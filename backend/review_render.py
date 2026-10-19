"""Measured narration timeline at 25 fps; immutable source clips with explicit freeze tails."""
import json
import os
import shutil
from .providers import ProviderError

def render(job,command,segments,audio,destination,directory,source_duration_ms):
    from .worker import FORMATS
    ffmpeg=os.getenv('DUBISUB_FFMPEG','ffmpeg');files=[]
    budget=min(int(os.getenv('DUBISUB_MAX_UPLOAD_MB','2048'))*1024**2,shutil.disk_usage(directory).free-128*1024**2)
    if budget<16*1024**2:raise ProviderError('Không đủ đĩa để dựng review.')
    from .review_scenes import detect,select_shots
    boundaries=detect(job,command,source_duration_ms)
    used=0
    for index,s in enumerate(segments):
        ranges,skipped=select_shots(s['source_ranges'],boundaries,source_duration_ms,s['output_end_ms']-s['start_ms'])
        if not ranges:raise ProviderError('Cảnh nguồn không nằm trong video đã chọn.')
        frames=round((s['output_end_ms']-s['start_ms'])/40)
        if frames<len(ranges):raise ProviderError('Lời dẫn quá ngắn để hiển thị đủ cảnh dẫn chứng. Gộp cảnh hoặc kéo dài lời dẫn.')
        total=sum(r['end_ms']-r['start_ms'] for r in ranges);remaining=frames
        minimum=max(1,min(20,frames//len(ranges)))
        extra=frames-minimum*len(ranges)
        s['render_source_ranges']=[];s['freeze_tail_ms']=0
        for part,source in enumerate(ranges):
            count=remaining if part==len(ranges)-1 else min(remaining-minimum*(len(ranges)-part-1),minimum+round(extra*(source['end_ms']-source['start_ms'])/total))
            remaining-=count;duration=count*40;start=source['start_ms'];available=source['end_ms']-start
            clip=directory/f'clip-{index:04d}-{part:04d}.mp4'
            vf=f'scale=640:360:force_original_aspect_ratio=decrease,pad=640:360:(ow-iw)/2:(oh-ih)/2,fps=25,tpad=stop_mode=clone:stop_duration={duration/1000},trim=duration={duration/1000},setpts=PTS-STARTPTS'
            command([ffmpeg,'-v','error','-nostdin','-ss',str(start/1000),'-t',str(min(available,duration)/1000),'-protocol_whitelist','file,pipe','-format_whitelist',FORMATS,'-i',job['path'],'-an','-vf',vf,'-c:v','libx264','-preset','veryfast','-threads','2','-pix_fmt','yuv420p','-fs',str(max(1,budget-used)),'-y',str(clip)],job,timeout=600)
            used+=clip.stat().st_size
            if used>=budget:raise ProviderError('Dựng review chạm giới hạn dung lượng.')
            files.append(clip.name)
            s['render_source_ranges'].append({'start_ms':start,'end_ms':start+min(available,duration),'output_duration_ms':duration})
            s['freeze_tail_ms']+=max(0,duration-available)
        s['render_source_range']=s['render_source_ranges'][0]
        s['scene_detection']={'method':'ffmpeg_scene_score','threshold':.35,'sample_fps':2,'unselected_shots':skipped,'limitations':'Chọn cảnh minh họa theo phân bố thời gian, đại diện mọi khoảng dẫn chứng rời nhau; không hiển thị mọi cảnh hoặc chứng minh đã hiểu toàn bộ nội dung. Duyệt kịch bản để giữ diễn biến.'}
    listing=directory/'clips.txt';listing.write_text(''.join(f"file '{name}'\n" for name in files),encoding='ascii')
    duration=segments[-1]['output_end_ms']/1000
    if shutil.disk_usage(directory).free<used+128*1024**2:raise ProviderError('Không đủ đĩa để ghép review.')
    command([ffmpeg,'-v','error','-nostdin','-f','concat','-safe','1','-protocol_whitelist','file,pipe','-i',str(listing),'-i',str(audio),'-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','aac','-af','apad','-t',str(duration),'-movflags','+faststart','-fs',str(budget),'-y',str(destination)],job,timeout=1800)
    probe=json.loads(command([os.getenv('DUBISUB_FFPROBE','ffprobe'),'-v','error','-show_format','-of','json',str(destination)],job))
    if abs(float(probe['format']['duration'])-duration)>.12:raise ProviderError('Video review chưa đủ thời lượng; không lưu bản xuất dở.')
