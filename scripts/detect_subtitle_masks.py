"""Local RapidOCR sample detector. Subprocess output is data, never code."""
import bisect
import contextlib
import importlib.metadata
import json
import sys
import cv2


def main():
    request=json.load(open(sys.argv[1],encoding='utf-8'))
    # Libraries may print startup details; keep stdout a bounded JSON contract.
    with contextlib.redirect_stdout(sys.stderr):
        from rapidocr_onnxruntime import RapidOCR
        engine=RapidOCR(intra_op_num_threads=2,inter_op_num_threads=1,det_limit_type='max',det_limit_side_len=960) if request.get('detector_profile')=='cpu_fast' else RapidOCR()
    cap=cv2.VideoCapture(request['path']);width=int(cap.get(cv2.CAP_PROP_FRAME_WIDTH));height=int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT));roi=request['roi']
    x=round(roi['x']*width);y=round(roi['y']*height);w=round(roi['width']*width);h=round(roi['height']*height)
    step=1000//request['fps'];output=[];previous=[];cuts=request['boundaries'];previous_scene=-1
    try:
        sequential=request.get('detector_version',1)>=2
        if sequential:cap.set(cv2.CAP_PROP_POS_MSEC,request['start_ms'])
        for timestamp in range(request['start_ms'],request['end_ms'],step):
            scene=bisect.bisect_right(cuts,timestamp)-1
            if scene!=previous_scene:previous=[]
            previous_scene=scene
            if sequential:
                ok=cap.grab();advances=0
                while ok and cap.get(cv2.CAP_PROP_POS_MSEC)<timestamp-.5:
                    ok=cap.grab();advances+=1
                    if advances>5000:raise ValueError('Frame timestamps do not advance safely.')
                ok,frame=cap.retrieve() if ok else (False,None)
            else:
                cap.set(cv2.CAP_PROP_POS_MSEC,timestamp);ok,frame=cap.read()
            if not ok:raise ValueError('Cannot decode sampled frame.')
            crop=frame[y:y+h,x:x+w];scale=min(1.,960/max(1,w));crop=cv2.resize(crop,None,fx=scale,fy=scale) if scale<1 else crop
            with contextlib.redirect_stdout(sys.stderr):result,_=engine(crop)
            current=[]
            for polygon,text,score in result or []:
                if score<.5:continue
                left=max(0,min(p[0] for p in polygon)/scale+x-5);top=max(0,min(p[1] for p in polygon)/scale+y-4)
                right=min(width,max(p[0] for p in polygon)/scale+x+5);bottom=min(height,max(p[1] for p in polygon)/scale+y+4)
                start=max(request['start_ms'],cuts[max(0,scene)],timestamp-100);end=min(request['end_ms'],cuts[min(len(cuts)-1,scene+1)],timestamp+step+100)
                row={'id':str(len(output)),'start_ms':start,'end_ms':end,'x':left/width,'y':top/height,'width':(right-left)/width,'height':(bottom-top)/height,'confidence':float(score),'needs_review':score<.85}
                match=next((old for old in previous if old['end_ms']>=start and abs(old['x']-row['x'])<.015 and abs(old['y']-row['y'])<.012 and abs(old['width']-row['width'])<.025 and abs(old['height']-row['height'])<.015),None)
                if match:
                    # Union prevents clipped letters while smoothing small OCR jitter.
                    r=max(match['x']+match['width'],row['x']+row['width']);b=max(match['y']+match['height'],row['y']+row['height']);match['x']=min(match['x'],row['x']);match['y']=min(match['y'],row['y']);match['width']=r-match['x'];match['height']=b-match['y'];match['end_ms']=end;match['confidence']=min(match['confidence'],row['confidence']);match['needs_review']|=row['needs_review'];current.append(match)
                else:output.append(row);current.append(row)
                if len(output)>3000:raise ValueError('Too many OCR regions; shorten the sample.')
            previous=current
    finally:cap.release()
    print(json.dumps({'regions':output,'detector':'rapidocr_onnxruntime','version':importlib.metadata.version('rapidocr-onnxruntime'),'profile':request.get('detector_profile','balanced'),'method':'sampled_text_boxes_with_scene_reset'}))


if __name__=='__main__':main()
