"""Measured narration timeline at 25 fps; immutable source clips with explicit freeze tails."""
import json
import os
import shutil
from .providers import ProviderError

def render(job,command,segments,audio,destination,directory,source_duration_ms,options=None):
    from .worker import FORMATS
    ffmpeg=os.getenv('DUBISUB_FFMPEG','ffmpeg');files=[]
    budget=min(int(os.getenv('DUBISUB_MAX_UPLOAD_MB','2048'))*1024**2,shutil.disk_usage(directory).free-128*1024**2)
    if budget<16*1024**2:raise ProviderError('Không đủ đĩa để dựng review.')
    from .review_scenes import detect,select_shots
    from .review_mapping import approved
    options=options or {};illustrative=options.get('review_edit_mode')=='illustrative'
    boundaries=detect(job,command,source_duration_ms) if illustrative else []
    used=0
    for index,s in enumerate(segments):
        if illustrative:ranges,skipped=select_shots(s['source_ranges'],boundaries,source_duration_ms,s['output_end_ms']-s['start_ms'])
        else:ranges=approved(s,source_duration_ms,options.get('allow_freeze',False));skipped=0
        if not ranges:raise ProviderError('Cảnh nguồn không nằm trong video đã chọn.')
        frames=round((s['output_end_ms']-s['start_ms'])/40)
        if frames<len(ranges):raise ProviderError('Lời dẫn quá ngắn để hiển thị đủ cảnh dẫn chứng. Gộp cảnh hoặc kéo dài lời dẫn.')
        total=sum(r['end_ms']-r['start_ms'] for r in ranges);remaining=frames
        minimum=max(1,min(20,frames//len(ranges)))
        extra=frames-minimum*len(ranges)
        s['render_source_ranges']=[];s['freeze_tail_ms']=0
        for part,source in enumerate(ranges):
            count=source['output_duration_ms']//40 if not illustrative else remaining if part==len(ranges)-1 else min(remaining-minimum*(len(ranges)-part-1),minimum+round(extra*(source['end_ms']-source['start_ms'])/total))
            remaining-=count;duration=count*40;start=source['start_ms'];available=source['end_ms']-start
            clip=directory/f'clip-{index:04d}-{part:04d}.mp4'
            if duration>available and not options.get('allow_freeze',False):raise ProviderError('Thiếu hình đã duyệt; không tự giữ hình cuối. Chọn cảnh khác hoặc bật rõ tùy chọn giữ hình.')
            from .rendering import normalize_plan,video_filter_args
            plan=normalize_plan({'in_ms':start,'out_ms':start+min(available,duration),'resolution':360,'fps':25,'subtitle_mask':options.get('subtitle_mask') or {'enabled':False}},source_duration_ms)
            plan.update(source_width=options.get('source_width'),source_height=options.get('source_height'))
            video_args=video_filter_args(plan,[],directory,False,tail_duration=duration/1000)
            command([ffmpeg,'-v','error','-nostdin','-ss',str(start/1000),'-t',str(min(available,duration)/1000),'-protocol_whitelist','file,pipe','-format_whitelist',FORMATS,'-i',job['path'],'-an',*video_args,'-c:v','libx264','-preset','veryfast','-threads','2','-pix_fmt','yuv420p','-fs',str(max(1,budget-used)),'-y',str(clip)],job,timeout=600,cwd=directory)
            used+=clip.stat().st_size
            if used>=budget:raise ProviderError('Dựng review chạm giới hạn dung lượng.')
            files.append(clip.name)
            s['render_source_ranges'].append({'start_ms':start,'end_ms':start+min(available,duration),'output_start_ms':source.get('output_start_ms'),'output_duration_ms':duration})
            s['freeze_tail_ms']+=max(0,duration-available)
        s['render_source_range']=s['render_source_ranges'][0]
        s['scene_detection']={'method':'illustrative_time_sampling' if illustrative else 'approved_source_ranges','unselected_shots':skipped,'limitations':'Cảnh theo ánh xạ đã duyệt; chế độ minh họa theo thời gian chỉ bật khi chọn rõ. Không mặc định lặp, freeze hoặc slow motion.'}
    listing=directory/'clips.txt';listing.write_text(''.join(f"file '{name}'\n" for name in files),encoding='ascii')
    duration=segments[-1]['output_end_ms']/1000
    if shutil.disk_usage(directory).free<used+128*1024**2:raise ProviderError('Không đủ đĩa để ghép review.')
    video_args=['-c:v','copy']
    if options.get('burn_subtitles'):
        from .subtitles import export
        cues=[{'id':s['id'],'text':s['text'],'start_ms':s['start_ms'],'end_ms':s['start_ms']+s['duration_ms']} for s in segments]
        (directory/'review-captions.ass').write_text(export(cues,'ass'),encoding='utf-8');video_args=['-vf','subtitles=filename=review-captions.ass:charenc=UTF-8','-c:v','libx264','-preset','veryfast','-threads','2']
    command([ffmpeg,'-v','error','-nostdin','-f','concat','-safe','1','-protocol_whitelist','file,pipe','-i',str(listing),'-i',str(audio),'-map','0:v:0','-map','1:a:0',*video_args,'-c:a','aac','-af','apad','-t',str(duration),'-movflags','+faststart','-fs',str(budget),'-y',str(destination)],job,timeout=1800,cwd=directory)
    probe=json.loads(command([os.getenv('DUBISUB_FFPROBE','ffprobe'),'-v','error','-show_format','-of','json',str(destination)],job))
    if abs(float(probe['format']['duration'])-duration)>.12:raise ProviderError('Video review chưa đủ thời lượng; không lưu bản xuất dở.')
