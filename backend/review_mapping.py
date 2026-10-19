"""Explicit source/output edit decisions reused for video, masks and source audio."""
import os
from .providers import ProviderError
from .review_scenes import select_ranges


def approved(segment,source_duration_ms,allow_freeze=False):
    ranges=select_ranges(segment['source_ranges'],[],source_duration_ms)
    frames=round((segment['output_end_ms']-segment['start_ms'])/40)
    available=[max(0,(r['end_ms']-r['start_ms'])//40) for r in ranges]
    if not ranges or any(n==0 for n in available) or frames<len(ranges):raise ProviderError('Cảnh đã duyệt quá ngắn hoặc quá nhiều. Sửa ánh xạ cảnh trong kịch bản trước khi dựng.')
    if sum(available)<frames and not allow_freeze:raise ProviderError('Thiếu hình trong cảnh đã duyệt. Chọn thêm/kéo dài cảnh; không tự lặp, giữ hình hoặc slow motion.')
    total=sum(available);remaining=frames;counts=[]
    for index,capacity in enumerate(available):
        reserve=len(ranges)-index-1;count=remaining if not reserve else max(1,min(remaining-reserve,round(frames*capacity/total)))
        if not allow_freeze:count=min(count,capacity)
        counts.append(count);remaining-=count
    for index in range(len(counts)):
        extra=min(remaining,max(0,available[index]-counts[index]));counts[index]+=extra;remaining-=extra
    if remaining:
        if not allow_freeze:raise ProviderError('Không đủ cảnh nguồn để khớp lời dẫn.')
        counts[-1]+=remaining
    cursor=segment['start_ms'];result=[]
    for source,count in zip(ranges,counts):
        length=min(count*40,source['end_ms']-source['start_ms'])
        result.append({'start_ms':source['start_ms'],'end_ms':source['start_ms']+length,'output_start_ms':cursor,'output_duration_ms':count*40});cursor+=count*40
    return result


def source_audio(source,ranges,destination,directory,job,command,stream=0):
    from .worker import FORMATS
    ffmpeg=os.getenv('DUBISUB_FFMPEG','ffmpeg');files=[]
    for index,r in enumerate(ranges):
        path=directory/f'bed-{destination.stem}-{index:04}.wav';duration=r['output_duration_ms']/1000
        command([ffmpeg,'-v','error','-nostdin','-ss',str(r['start_ms']/1000),'-t',str((r['end_ms']-r['start_ms'])/1000),'-protocol_whitelist','file,pipe','-format_whitelist',FORMATS,'-i',str(source),'-map',f'0:a:{stream}','-af',f'apad=whole_dur={duration}','-t',str(duration),'-ac','2','-ar','48000','-c:a','pcm_s16le','-y',str(path)],job)
        files.append(path.name)
    listing=directory/f'{destination.stem}.txt';listing.write_text(''.join(f"file '{name}'\n" for name in files),encoding='ascii')
    command([ffmpeg,'-v','error','-nostdin','-f','concat','-safe','1','-protocol_whitelist','file,pipe','-i',str(listing),'-c:a','copy','-y',str(destination)],job)


def mix_audio(job,command,segments,dry,output,directory,payload,bed_source,vocal_source=None):
    from .audio_mix import render as mix
    ranges=[]
    for segment in segments:
        selected=approved(segment,payload['source_duration_ms'],payload.get('allow_freeze',False));segment['render_source_ranges']=selected;ranges.extend(selected)
    plan=payload['audio_mix'];bed=directory/'review-bed.wav'
    source_audio(bed_source,ranges,bed,directory,job,command,plan.get('audio_stream',0) if plan['mode']!='separated' else 0)
    vocal=None
    if vocal_source and plan.get('vocal_volume',0)>0:
        vocal=directory/'review-vocals.wav';source_audio(vocal_source,ranges,vocal,directory,job,command)
    mix(bed,dry,output,{**plan,'audio_stream':0},segments[-1]['output_end_ms'],job,command,vocal)
