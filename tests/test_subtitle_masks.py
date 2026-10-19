import json
import subprocess
import pytest
from backend.subtitle_masks import regions,attach
from backend.rendering import normalize_plan,video_filter_args


def test_region_bounds_and_review_gate():
    row={'start_ms':100,'end_ms':900,'x':.1,'y':.7,'width':.5,'height':.1}
    assert regions([row],1000)[0]['end_ms']==900
    for patch in [{'end_ms':1001},{'x':float('nan')},{'width':2}]:
        with pytest.raises(ValueError):regions([{**row,**patch}],1000)
    doc={'subtitle_masks':{'m':{'asset_id':'a','reviewed':False,'regions':[row]}}}
    with pytest.raises(ValueError):attach(doc,'a',{'track_id':'m'},1000)
    doc['subtitle_masks']['m']['reviewed']=True
    assert attach(doc,'a',{'track_id':'m'},1000)['mode']=='tracked'
    with pytest.raises(ValueError):attach(doc,'other',{'track_id':'m'},1000)


def test_real_timed_mask_does_not_blur_whole_video_or_outside_box(tmp_path):
    source=tmp_path/'source.mp4';output=tmp_path/'masked.mp4'
    subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','testsrc2=s=320x180:r=24:d=3','-c:v','libx264','-y',str(source)],check=True)
    plan=normalize_plan({'resolution':360,'subtitle_mask':{'enabled':True,'mode':'tracked','strength':8,'regions':[{'start_ms':1000,'end_ms':2000,'x':.2,'y':.6,'width':.6,'height':.2}]}},3000)
    plan.update(source_width=320,source_height=180)
    args=video_filter_args(plan,[],tmp_path,False)
    subprocess.run(['ffmpeg','-v','error','-i',str(source),*args,'-c:v','libx264','-y',str(output)],cwd=tmp_path,check=True)
    # Compare against the same transform/encoder without masks, sampling pixels
    # over entire frames catches a matte accidentally opaque outside active time.
    control=tmp_path/'control.mp4';base=normalize_plan({'resolution':360},3000)
    subprocess.run(['ffmpeg','-v','error','-i',str(source),*video_filter_args(base,[],tmp_path,False),'-c:v','libx264','-y',str(control)],check=True)
    import numpy as np
    def frame(path,time):
        raw=subprocess.check_output(['ffmpeg','-v','error','-ss',str(time),'-i',str(path),'-frames:v','1','-f','rawvideo','-pix_fmt','gray','pipe:1'])
        return np.frombuffer(raw,dtype=np.uint8).reshape(360,640).astype(float)
    before=np.abs(frame(output,.5)-frame(control,.5)).mean()
    active=np.abs(frame(output,1.5)-frame(control,1.5))
    after=np.abs(frame(output,2.5)-frame(control,2.5)).mean()
    assert before<2 and after<2
    assert active[220:280,140:500].mean()>5
    assert active[:150,:].mean()<2
