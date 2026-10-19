"""Versioned single-source render plan, shared with source preview time mapping."""
import json
import math
import os
import shutil
import time
from pathlib import Path
from . import store
from .subtitles import export


def normalize_plan(raw, duration_ms):
    start=raw.get('in_ms',0);end=raw.get('out_ms',duration_ms);speed=raw.get('speed',1)
    if not isinstance(start,int) or isinstance(start,bool) or not isinstance(end,int) or isinstance(end,bool) or not 0<=start<end<=duration_ms:
        raise ValueError('Vùng xuất phải nằm trong thời lượng nguồn và có kết thúc sau bắt đầu.')
    if not isinstance(speed,(int,float)) or isinstance(speed,bool) or not math.isfinite(speed) or not .5<=speed<=2:
        raise ValueError('Tốc độ phải từ 0.5 đến 2 lần.')
    aspect=raw.get('aspect','16:9');resolution=raw.get('resolution',720);fps=raw.get('fps',24);volume=raw.get('volume',1)
    if aspect not in ('16:9','9:16','1:1') or resolution not in (360,720,1080) or fps not in (24,25,30):raise ValueError('Preset xuất không được hỗ trợ.')
    if not isinstance(volume,(int,float)) or isinstance(volume,bool) or not math.isfinite(volume) or not 0<=volume<=2:raise ValueError('Âm lượng phải từ 0 đến 2 lần.')
    mask=raw.get('subtitle_mask',{'enabled':False,'x':.05,'y':.74,'width':.9,'height':.24,'strength':8})
    if not isinstance(mask,dict) or not isinstance(mask.get('enabled'),bool):raise ValueError('Thiết lập vùng làm mờ không hợp lệ.')
    mask={k:mask.get(k,v) for k,v in {'enabled':False,'x':.05,'y':.74,'width':.9,'height':.24,'strength':8}.items()}
    if any(isinstance(mask[k],bool) or not isinstance(mask[k],(int,float)) or not math.isfinite(mask[k]) for k in ('x','y','width','height','strength')):raise ValueError('Vùng làm mờ cần số hữu hạn.')
    if not (0<=mask['x']<=.98 and 0<=mask['y']<=.98 and .02<=mask['width']<=1 and .02<=mask['height']<=1 and mask['x']+mask['width']<=1.000001 and mask['y']+mask['height']<=1.000001 and 1<=mask['strength']<=30):raise ValueError('Vùng làm mờ phải nằm trong khung nguồn; cường độ 1–30.')
    w,h={'16:9':(resolution*16//9,resolution),'9:16':(resolution,resolution*16//9),'1:1':(resolution,resolution)}[aspect]
    w+=w%2;h+=h%2
    return {'schema_version':1,'in_ms':start,'out_ms':end,'speed':float(speed),'aspect':aspect,'resolution':resolution,'fps':fps,'volume':float(volume),
            'width':w,'height':h,'duration_ms':round((end-start)/speed),'fit':'contain','subtitle_mask':mask}


def output_cues(cues, plan):
    result=[]
    for cue in cues:
        start=max(cue['start_ms'],plan['in_ms']);end=min(cue['end_ms'],plan['out_ms'])
        if end<=start:continue
        result.append({**cue,'start_ms':round((start-plan['in_ms'])/plan['speed']),'end_ms':round((end-plan['in_ms'])/plan['speed'])})
    return [c for c in result if c['end_ms']>c['start_ms']]


def video_filter_args(plan,cues,directory,burn_subtitles):
    filters=f"setpts=(PTS-STARTPTS)/{plan['speed']},scale={plan['width']}:{plan['height']}:force_original_aspect_ratio=decrease,pad={plan['width']}:{plan['height']}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1,fps={plan['fps']}"
    if burn_subtitles:
        # Local generated ASS uses plain text and an internal fixed path, never an untrusted filter expression.
        (directory/'captions.ass').write_text(export(cues,'ass'),encoding='utf-8')
        filters+=',subtitles=filename=captions.ass:charenc=UTF-8'
    mask=plan.get('subtitle_mask',{})
    if mask.get('enabled'):
        graph=f"[0:v:0]split[base][region];[region]crop=w='max(2,trunc(iw*{mask['width']}/2)*2)':h='max(2,trunc(ih*{mask['height']}/2)*2)':x=iw*{mask['x']}:y=ih*{mask['y']},boxblur=luma_radius='max(0,min({mask['strength']},min(w,h)/2-1))':luma_power=2[blurred];[base][blurred]overlay=x=main_w*{mask['x']}:y=main_h*{mask['y']},{filters}[vout]"
        video_args=['-filter_complex',graph,'-map','[vout]']
    else:video_args=['-vf',filters,'-map','0:v:0']
    return video_args


def execute(job, command):
    payload=json.loads(job['payload']);plan=payload['plan'];directory=store.root()/'render-staging'/job['id'];directory.mkdir(parents=True,exist_ok=True)
    final=store.root()/'artifacts'/f'{job["id"]}.mp4';final.parent.mkdir(exist_ok=True)
    expected=plan['duration_ms']/1000*1024**2
    if shutil.disk_usage(directory).free<expected+128*1024**2:raise ValueError('Không đủ dung lượng dự phòng để render video.')
    cues=output_cues(payload.get('cues',[]),plan)
    video_args=video_filter_args(plan,cues,directory,payload.get('burn_subtitles',False))
    partial=directory/'render.mp4'
    args=[os.getenv('DUBISUB_FFMPEG','ffmpeg'),'-v','error','-nostdin','-ss',str(plan['in_ms']/1000),'-t',str((plan['out_ms']-plan['in_ms'])/1000),'-protocol_whitelist','file,pipe',
          '-format_whitelist','mov,matroska,webm,avi,mp3,wav,flac,ogg,mpegts,mpeg,aac','-i',job['path'],
          *video_args,'-map','0:a:0?','-af',f"atempo={plan['speed']},volume={plan['volume']}",
          '-c:v','libx264','-preset','veryfast','-crf','20','-threads','2','-pix_fmt','yuv420p','-c:a','aac','-movflags','+faststart',
          '-fs',str(int(os.getenv('DUBISUB_MAX_UPLOAD_MB','2048'))*1024**2),'-y',str(partial)]
    command(args,job,timeout=10800,cwd=directory)
    probe=json.loads(command([os.getenv('DUBISUB_FFPROBE','ffprobe'),'-v','error','-show_format','-show_streams','-of','json',str(partial)],job))
    actual=float(probe.get('format',{}).get('duration',0))*1000
    if abs(actual-plan['duration_ms'])>max(150,2000/plan['fps']):raise ValueError('Render bị thiếu thời lượng hoặc vượt giới hạn file; không lưu bản xuất chưa hoàn tất.')
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        if not db.execute("SELECT id FROM jobs WHERE id=? AND state='running' AND owner=?",(job['id'],job['owner'])).fetchone():raise ValueError('Tác vụ render đã bị hủy.')
        doc=store.project(db,job['project_id'])
        partial.replace(final)
        try:
            artifacts=doc.setdefault('artifacts',[])
            artifacts[:]=[a for a in artifacts if a['job_id']!=job['id']]
            artifacts.append({'id':job['id'],'job_id':job['id'],'kind':'video','filename':'dubisub-export.mp4','size':final.stat().st_size,'plan':plan,'created_at':time.time(),'track_id':payload.get('track_id'),'source_revision':payload['source_revision']})
            store.save(db,doc)
            db.execute("UPDATE jobs SET state='succeeded',progress=100,error=NULL,checkpoint='render-committed' WHERE id=?",(job['id'],))
        except BaseException:
            final.unlink(missing_ok=True);raise
