"""A single measured stereo mix shared by playback/download and video muxing."""
import math
import os


def normalize(raw):
    if not isinstance(raw,dict):raise ValueError('Kế hoạch phối âm không hợp lệ.')
    plan={'mode':raw.get('mode','replace'),'source_volume':raw.get('source_volume',.35),
          'voice_volume':raw.get('voice_volume',1.),'ducking':raw.get('ducking',True),
          'audio_stream':raw.get('audio_stream',0),'stem_id':raw.get('stem_id',''),'vocal_volume':raw.get('vocal_volume',0.)}
    if plan['mode'] not in ('replace','voiceover','separated'):raise ValueError('Chọn chỉ giọng mới, thuyết minh hoặc nền đã tách thật.')
    if not isinstance(plan['stem_id'],str) or len(plan['stem_id'])>100:raise ValueError('ID stem không hợp lệ.')
    if any(isinstance(plan[k],bool) or not isinstance(plan[k],(float,int)) or not math.isfinite(plan[k]) or not 0<=plan[k]<=2 for k in ('source_volume','voice_volume','vocal_volume')):raise ValueError('Âm lượng phải từ 0 đến 2.')
    if not isinstance(plan['ducking'],bool) or type(plan['audio_stream']) is not int or not 0<=plan['audio_stream']<=32:raise ValueError('Track audio/ducking không hợp lệ.')
    return {'schema_version':1,**plan}


def render(source,voice,destination,raw,duration_ms,job,command,original_voice=None):
    from .worker import FORMATS
    plan=normalize(raw);duration=duration_ms/1000
    voice_filter=f"aresample=48000,aformat=channel_layouts=stereo,volume={plan['voice_volume']},apad,atrim=duration={duration}"
    args=[os.getenv('DUBISUB_FFMPEG','ffmpeg'),'-v','error','-nostdin']
    if plan['mode'] in ('voiceover','separated'):
        args+=['-protocol_whitelist','file,pipe','-format_whitelist',FORMATS,'-i',str(source),'-i',str(voice)]
        stream=plan['audio_stream'] if plan['mode']=='voiceover' else 0
        graph=f"[0:a:{stream}]aresample=48000,aformat=channel_layouts=stereo,volume={plan['source_volume']},apad,atrim=duration={duration}[bed];[1:a:0]{voice_filter}[voice];"
        extra='';count=2
        if plan['mode']=='separated' and plan['vocal_volume']>0:
            if not original_voice:raise ValueError('Thiếu stem giọng gốc; không dùng bản mix gốc thay thế ngầm.')
            args+=['-i',str(original_voice)];graph+=f"[2:a:0]aresample=48000,aformat=channel_layouts=stereo,volume={plan['vocal_volume']},apad,atrim=duration={duration}[originalvoice];";extra='[originalvoice]';count=3
        if plan['ducking']:
            graph+='[voice]asplit[narration][side];[bed][side]sidechaincompress=threshold=0.025:ratio=6:attack=20:release=250[ducked];[ducked][narration]'
        else:graph+='[bed][voice]'
        graph+=extra+f'amix=inputs={count}:duration=longest:normalize=0,alimiter=limit=0.95:level=0:latency=1[mix]'
        args+=['-filter_complex',graph,'-map','[mix]']
    else:
        args+=['-i',str(voice),'-af',voice_filter+',alimiter=limit=0.95:level=0:latency=1']
    command([*args,'-t',str(duration),'-ac','2','-ar','48000','-c:a','pcm_s16le','-y',str(destination)],job,timeout=3600)
