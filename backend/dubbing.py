"""Explicit-consent reference voices and checkpointed subtitle narration."""
import sys
from array import array
import hashlib
import json
import math
import os
import shutil
import time
import wave
import langcodes
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit
from fastapi import APIRouter,HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel,Field,field_validator
from . import store
from .providers import configured,request,ProviderError
from .voices import synthesize,catalog
from .ai_tasks import fingerprint,context_current
router=APIRouter(prefix='/api')

def pcm_samples(data):
    samples=array('h',data)
    if sys.byteorder!='little':samples.byteswap()
    return samples

def pcm_add(left,right):
    samples=array('h',(max(-32768,min(32767,a+b)) for a,b in zip(pcm_samples(left),pcm_samples(right))))
    if sys.byteorder!='little':samples.byteswap()
    return samples.tobytes()

def pcm_rms(data):
    samples=pcm_samples(data)
    return math.sqrt(sum(value*value for value in samples)/max(1,len(samples)))


def _capability(provider):
    if provider.get('protocol','openai')!='openai' or provider['model']!='vieneu-v3-turbo':
        raise ProviderError('Cloning hiện hỗ trợ adapter VieNeu v3 Turbo đã xác minh, không suy đoán từ tên endpoint.')
    models=request(provider,'models',timeout=10)
    if not isinstance(models,dict) or not any(isinstance(m,dict) and m.get('id')=='vieneu-v3-turbo' for m in models.get('data',[])):
        raise ProviderError('Endpoint không công bố model VieNeu v3 Turbo.')
    if not provider['endpoint'].rstrip('/').endswith('/v1'):raise ProviderError('Adapter cần endpoint VieNeu kết thúc bằng /v1.')
    root={**provider,'endpoint':provider['endpoint'].rstrip('/')[:-3]}
    schema=request(root,'openapi.json',timeout=10)
    post=schema.get('paths',{}).get('/v1/voices',{}).get('post',{}) if isinstance(schema,dict) else {}
    ref=post.get('requestBody',{}).get('content',{}).get('multipart/form-data',{}).get('schema',{}).get('$ref','').split('/')[-1]
    props=schema.get('components',{}).get('schemas',{}).get(ref,{}).get('properties',{}) if isinstance(schema,dict) else {}
    if not {'name','file','denoise'}.issubset(props):raise ProviderError('Endpoint này không công bố API đăng ký giọng mẫu tương thích.')
    return {'cloning':True,'languages':['vi'],'sample_rate':48000,'reference_min_ms':3000,'reference_max_ms':8000,'provider':provider['endpoint'],'model':provider['model'],'remote_voice_delete':False,'provider_fingerprint':fingerprint(provider)}

def capability(provider):
    try:return _capability(provider)
    except (AttributeError,TypeError,KeyError):raise ProviderError('Provider trả metadata cloning không hợp lệ.') from None

@router.get('/voice-capabilities')
def capabilities():
    p=configured('tts')
    try:return {**capability(p),'mix_schema_version':1}
    except ProviderError as e:return {'cloning':False,'languages':[],'provider':p['endpoint'],'model':p['model'],'reason':str(e)}

class Reference(BaseModel):
    asset_id:str
    name:str=Field(min_length=1,max_length=100)
    start_ms:int=Field(ge=0)
    end_ms:int=Field(gt=0)
    audio_stream:int=Field(default=0,ge=0,le=32)
    permission_confirmed:bool=False
    clean_sample_confirmed:bool=False

@router.post('/projects/{pid}/voice-profiles',status_code=202)
def reference(pid:str,body:Reference):
    if not body.permission_confirmed:raise HTTPException(422,'Xác nhận bạn sở hữu hoặc được phép dùng giọng mẫu.')
    if not body.clean_sample_confirmed:raise HTTPException(422,'Nghe lại và xác nhận đoạn sạch, chỉ một người nói; chưa có bộ phát hiện nhạc/nhiều giọng tự động.')
    if not 3000<=body.end_ms-body.start_ms<=8000:raise HTTPException(422,'Đoạn giọng phải dài từ 3 đến 8 giây.')
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE');store.project(db,pid)
        row=db.execute("SELECT metadata FROM assets WHERE id=? AND project_id=? AND kind='media'",(body.asset_id,pid)).fetchone()
        meta=json.loads(row[0]) if row and row[0] else {}
        streams=[s for s in meta.get('streams',[]) if s.get('codec_type')=='audio']
        if body.audio_stream>=len(streams) or body.end_ms>float(meta.get('format',{}).get('duration',0))*1000:raise HTTPException(422,'Đoạn mẫu nằm ngoài media/audio đã kiểm tra.')
        jid=store.uid();payload={**body.model_dump(),'profile_id':store.uid(),'schema_version':1}
        db.execute("INSERT INTO jobs(id,project_id,asset_id,kind,payload) VALUES(?,?,?,'voice_extract',?)",(jid,pid,body.asset_id,json.dumps(payload)))
    return {'job_id':jid,'profile_id':payload['profile_id']}

@router.get('/projects/{pid}/voice-profiles/{profile_id}/audio')
def reference_audio(pid:str,profile_id:str):
    with store.connect() as db:doc=store.project(db,pid)
    if profile_id not in doc.get('voice_profiles',{}):raise KeyError(profile_id)
    return FileResponse(store.root()/'voice-profiles'/f'{profile_id}.wav',media_type='audio/wav')

@router.delete('/projects/{pid}/voice-profiles/{profile_id}')
def delete_reference(pid:str,profile_id:str):
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE');doc=store.project(db,pid)
        if profile_id not in doc.get('voice_profiles',{}):raise KeyError(profile_id)
        del doc['voice_profiles'][profile_id]
        # Cancel snapshots using this profile before removing derived files.
        for row in db.execute("SELECT id,payload FROM jobs WHERE project_id=? AND state IN ('queued','running')",(pid,)).fetchall():
            if profile_id in json.dumps(json.loads(row['payload'])):db.execute("UPDATE jobs SET state='canceled',error='Đã xóa hồ sơ giọng' WHERE id=?",(row['id'],))
        retained=[]
        for item in doc.get('dubbings',[]):
            if profile_id in item.get('profile_ids',[]):
                for ext in ('wav','voice.wav','mp4'):(store.root()/'dubbings'/f"{item['id']}.{ext}").unlink(missing_ok=True)
            else:retained.append(item)
        doc['dubbings']=retained
        settings=doc.setdefault('narration_settings',{})
        for track_id,value in list(settings.items()):
            if value.get('voice',{}).get('id')==profile_id or any(v.get('id')==profile_id for v in value.get('speakers',{}).values()):del settings[track_id]
        cache=doc.setdefault('dubbing_cache',{})
        for key,entry in list(cache.items()):
            if entry.get('profile_id')==profile_id:
                (store.root()/'dubbing-cache'/f'{key}.wav').unlink(missing_ok=True);del cache[key]
        store.save(db,doc)
    (store.root()/'voice-profiles'/f'{profile_id}.wav').unlink(missing_ok=True)
    return {'deleted':True,'provider_warning':'Đã xóa mẫu và dữ liệu dẫn xuất tại DubiSub. API VieNeu hiện chỉ lưu embedding trong RAM và không có DELETE; embedding đã gửi tồn tại đến khi chủ dịch vụ khởi động lại.'}

class Voice(BaseModel):
    kind:Literal['preset','profile']
    id:str=Field(min_length=1,max_length=160)

class Narration(BaseModel):
    language:str=Field(default='vi',max_length=40)
    @field_validator('language')
    @classmethod
    def normalize_language(cls,value):
        if not langcodes.tag_is_valid(value) or value.split('-')[0].lower()!='vi':raise ValueError('Adapter cloning hiện chỉ bật tiếng Việt (vi).')
        return langcodes.standardize_tag(value)
    revision:int
    track_id:str|None=None
    analysis_id:str|None=None
    text:str=Field(default='',max_length=300)
    voice:Voice
    speakers:dict[str,Voice]=Field(default_factory=dict,max_length=30)
    cue_speakers:dict[str,str]=Field(default_factory=dict,max_length=300)
    cue_ids:list[str]|None=Field(default=None,max_length=300)
    transfer_confirmed:bool=False
    provider_fingerprint:str=''
    export_video:bool=False
    fit_timing:bool=False
    burn_subtitles:bool=False
    subtitle_mask:dict=Field(default_factory=dict)
    audio_mix:dict=Field(default_factory=dict)
    review_edit_mode:Literal['approved','illustrative']='approved'
    allow_freeze:bool=False
    asset_id:str|None=None

@router.post('/projects/{pid}/narrations',status_code=202)
def narration(pid:str,body:Narration):
    from .audio_mix import normalize as normalize_mix
    mix_plan=normalize_mix(body.audio_mix)
    if body.analysis_id and body.track_id:raise HTTPException(422,'Chọn kịch bản hoặc track phụ đề, không chọn cả hai.')
    provider=configured('tts')
    if not body.transfer_confirmed:raise HTTPException(422,'Xác nhận gửi văn bản và đoạn giọng mẫu tới provider được hiển thị.')
    if body.provider_fingerprint!=fingerprint(provider):raise HTTPException(409,'Cấu hình TTS đã thay đổi. Kiểm tra lại VieNeu/provider và xác nhận truyền dữ liệu cho cấu hình mới.')
    capability(provider)
    allowed_presets={v['id'] for v in catalog(provider) if 'vi' in v['languages']}
    if any(v.kind=='preset' and v.id not in allowed_presets for v in [body.voice,*body.speakers.values()]):raise HTTPException(422,'Giọng preset không tồn tại hoặc chưa công bố hỗ trợ tiếng Việt.')
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE');doc=store.project(db,pid)
        if doc['revision']!=body.revision:raise HTTPException(409,'Dự án đã thay đổi. Lưu và mở lại trước khi tạo giọng.')
        if db.execute("SELECT id FROM jobs WHERE project_id=? AND kind='narrate' AND state IN ('queued','running')",(pid,)).fetchone():raise HTTPException(409,'Dự án đang tạo lời đọc. Chờ hoàn tất hoặc hủy trước khi tạo tiếp.')
        track=next((t for t in doc['tracks'] if t['id']==body.track_id),None)
        if body.track_id and not track:raise HTTPException(422,'Không tìm thấy track.')
        review=None
        if body.analysis_id:
            if mix_plan['mode']!='replace' and body.review_edit_mode!='approved':raise HTTPException(422,'Phối âm review cần ánh xạ cảnh đã duyệt, không dùng chọn cảnh minh họa theo thời gian.')
            if body.fit_timing:raise HTTPException(422,'Căn theo video nguồn chỉ dùng cho track dịch; review có timeline riêng.')
            review=doc.get('analyses',{}).get(body.analysis_id)
            if not review or review['kind'] not in ('review','summary','describe') or not review['reviewed']:raise HTTPException(422,'Chọn kịch bản đã duyệt trước khi tạo lời dẫn.')
            if review.get('language','und').split('-')[0]!='vi':raise HTTPException(422,'Adapter lời dẫn hiện chỉ bật tiếng Việt.')
            if review.get('source_track_id'):
                original=next((t for t in doc['tracks'] if t['id']==review['source_track_id']),None)
                if not original or fingerprint(original['cues'])!=review['source_hash']:raise HTTPException(409,'Transcript đã đổi; phân tích và duyệt lại kịch bản.')
            # Input contains source evidence, never invented output timestamps.
            cues=[{'id':r['id'],'text':r['text'],'start_ms':min(t['start_ms'] for t in r['source_ranges']),'end_ms':max(t['end_ms'] for t in r['source_ranges']),'source_ranges':r.get('clip_ranges') or r['source_ranges']} for r in review['items']]
        elif track:
            if track.get('kind')=='translation':
                from .ai_tasks import validate_target_text
                validate_target_text(track['cues'],track['language'],track.get('glossary',{}))
            if track.get('kind')=='review':raise HTTPException(422,'Sửa và đọc lại kịch bản gốc để tạo lại timeline review; không dùng lại timing review như nguồn.')
            if track['language']!='und' and track['language'].split('-')[0].lower()!='vi':raise HTTPException(422,'Adapter đã xác minh hiện chỉ bật tiếng Việt (vi).')
            if track.get('kind') in ('translation','asr') and not track.get('reviewed'):raise HTTPException(422,'Duyệt nội dung ASR/bản dịch trước khi tạo giọng.')
            if track.get('source_track_id'):
                source=next((t for t in doc['tracks'] if t['id']==track['source_track_id']),None)
                if not source or fingerprint(source['cues'])!=track.get('source_hash') or not context_current(doc,track):raise HTTPException(409,'Track nguồn đã thay đổi; cần dịch và duyệt lại.')
            cues=[c for c in track['cues'] if body.cue_ids is None or c['id'] in body.cue_ids]
            if body.cue_ids and set(body.cue_ids)!={c['id'] for c in cues}:raise HTTPException(422,'ID câu đã chọn không hợp lệ.')
        else:cues=[{'id':'text','start_ms':0,'end_ms':10000,'text':body.text}]
        if not cues or len(cues)>300 or any(not c['text'].strip() or len(c['text'])>300 for c in cues):raise HTTPException(422,'Mỗi tác vụ nhận 1–300 câu, mỗi câu tối đa 300 ký tự; sửa/tách câu dài trước khi tạo giọng.')
        voices=[body.voice,*body.speakers.values()];profiles={}
        for voice in voices:
            if voice.kind=='profile':
                if voice.id not in doc.get('voice_profiles',{}):raise HTTPException(422,'Hồ sơ giọng không còn tồn tại.')
                profiles[voice.id]=doc['voice_profiles'][voice.id]
        if any(v not in body.speakers for v in body.cue_speakers.values()):raise HTTPException(422,'Nhân vật chưa được gán giọng.')
        aid=body.asset_id
        if review and aid:
            origin=next((t for t in doc['tracks'] if t['id']==review.get('source_track_id')),{});source_aid=review.get('asset_id') or origin.get('asset_id')
            source_row=db.execute("SELECT id FROM assets WHERE id=? AND kind='media'",(source_aid,)).fetchone()
            if source_row and source_aid!=aid:raise HTTPException(422,'Video đã chọn khác nguồn bằng chứng kịch bản. Chọn đúng nguồn trước khi dựng review.')
        source_width=source_height=0
        if body.export_video or mix_plan['mode'] in ('voiceover','separated'):
            media=db.execute("SELECT metadata FROM assets WHERE id=? AND project_id=? AND kind='media'",(aid,pid)).fetchone()
            meta=json.loads(media[0]) if media and media[0] else {}
            if body.export_video and not any(s.get('codec_type')=='video' for s in meta.get('streams',[])):raise HTTPException(422,'Chọn nguồn video đã kiểm tra để xuất.')
            if mix_plan['mode']=='voiceover' and len([s for s in meta.get('streams',[]) if s.get('codec_type')=='audio'])<=mix_plan['audio_stream']:raise HTTPException(422,'Nguồn không có track audio đã chọn. Chọn chỉ giọng mới hoặc kiểm tra nguồn.')
            source_duration_ms=round(float(meta.get('format',{}).get('duration',0))*1000)
            if not 0<source_duration_ms<=7200000:raise HTTPException(422,'Xuất lồng tiếng hiện nhận video tối đa 2 giờ.')
            if body.subtitle_mask:
                from .rendering import normalize_plan
                from .subtitle_masks import attach
                body.subtitle_mask=attach(doc,aid,body.subtitle_mask,source_duration_ms)
                normalize_plan({'subtitle_mask':body.subtitle_mask},source_duration_ms)
            video_meta=next((s for s in meta.get('streams',[]) if s.get('codec_type')=='video'),{})
            source_width=video_meta.get('width',0);source_height=video_meta.get('height',0)
        else:source_duration_ms=0
        stem_id=None
        if mix_plan['mode']=='separated':
            stem_id=mix_plan['stem_id'];stem=doc.get('audio_stems',{}).get(stem_id)
            if not stem or stem['asset_id']!=aid or not stem.get('reviewed') or stem['start_ms']!=0 or abs(stem['end_ms']-source_duration_ms)>50:raise HTTPException(422,'Cần bản stems đã duyệt, bao phủ đúng toàn bộ video nguồn. Mẫu ngắn không được dùng thay nền cả phim.')
        if not aid:
            aid=store.uid();db.execute('INSERT INTO assets VALUES(?,?,?,?,?,?,NULL)',(aid,pid,'Lời đọc','','generated',''))
        elif not db.execute('SELECT id FROM assets WHERE id=? AND project_id=?',(aid,pid)).fetchone():raise HTTPException(422,'Media không thuộc dự án.')
        if any(c['end_ms']>7200000 for c in cues):raise HTTPException(422,'Timeline lời đọc hiện giới hạn 2 giờ.')
        if body.track_id:
            doc.setdefault('narration_settings',{})[body.track_id]={'voice':body.voice.model_dump(),'speakers':{k:v.model_dump() for k,v in body.speakers.items()},'cue_speakers':body.cue_speakers,'language':body.language,'audio_mix':mix_plan}
            store.save(db,doc)
        jid=store.uid();payload={**body.model_dump(),'audio_mix':mix_plan,'provider':provider,'profiles':profiles,'cues':cues,'source_revision':doc['revision'],'language':body.language,'source_duration_ms':source_duration_ms,'review_hash':fingerprint(review) if review else None}
        payload.update(source_width=source_width,source_height=source_height)
        payload['stem_id']=stem_id
        db.execute("INSERT INTO jobs(id,project_id,asset_id,kind,payload) VALUES(?,?,?,'narrate',?)",(jid,pid,aid,json.dumps(payload)))
    return {'job_id':jid}

@router.get('/projects/{pid}/narrations/{jid}/{kind}')
def narration_file(pid:str,jid:str,kind:Literal['audio','voice','video','srt','vtt','ass']):
    with store.connect() as db:doc=store.project(db,pid)
    artifact=next((d for d in doc.get('dubbings',[]) if d['id']==jid),None)
    if not artifact or kind=='video' and not artifact.get('video'):raise KeyError(jid)
    if kind in ('srt','vtt','ass'):
        from fastapi.responses import Response
        from .subtitles import export
        cues=artifact.get('subtitle_cues') or [{'id':s['id'],'text':s['text'],'start_ms':s['start_ms'],'end_ms':s['start_ms']+s['duration_ms']} for s in artifact['segments']]
        return Response(export(cues,kind),media_type='text/plain; charset=utf-8',headers={'Content-Disposition':f'attachment; filename="dubisub-dubbed.{kind}"'})
    if kind=='voice' and not artifact.get('dry_voice'):raise KeyError(jid)
    ext='voice.wav' if kind=='voice' else 'wav' if kind=='audio' else 'mp4'
    return FileResponse(store.root()/'dubbings'/f'{jid}.{ext}',media_type='video/mp4' if ext=='mp4' else 'audio/wav',filename='dubisub-narration.'+ext)

def active(job):
    if time.monotonic()>job.get('_deadline',float('inf')):raise ProviderError('Tác vụ giọng đã hết thời gian 3 giờ.')
    with store.connect() as db:
        if not db.execute("SELECT id FROM jobs WHERE id=? AND owner=? AND state='running'",(job['id'],job['owner'])).fetchone():raise ProviderError('Đã hủy tác vụ giọng.')

def register(provider,profile_id):
    with (store.root()/'voice-profiles'/f'{profile_id}.wav').open('rb') as audio:
        name='dubisub_'+profile_id.replace('-','')
        result=request(provider,'voices',files={'file':('reference.wav',audio,'audio/wav')},data={'name':name,'denoise':'true','description':'DubiSub user-confirmed reference'},timeout=180)
    if not isinstance(result,dict) or result.get('id')!=name:raise ProviderError('VieNeu không xác nhận đăng ký giọng.')
    return name

def mix(segments,destination,job):
    end=max(s['start_ms']+s['duration_ms'] for s in segments)
    if end>7200000:raise ProviderError('Xuất lời đọc hiện giới hạn timeline 2 giờ.')
    frames=math.ceil(end*48)
    if frames*2>int(os.getenv('DUBISUB_MAX_UPLOAD_MB','2048'))*1024**2:raise ProviderError('Audio xuất vượt giới hạn dung lượng.')
    if shutil.disk_usage(destination.parent).free<frames*2+128*1024**2:raise ProviderError('Không đủ đĩa để phối audio.')
    with wave.open(str(destination),'wb') as out:
        out.setnchannels(1);out.setsampwidth(2);out.setframerate(48000)
        for start in range(0,frames,48000):
            active(job);count=min(48000,frames-start);block=b'\0'*(count*2)
            for s in segments:
                at=round(s['start_ms']*48);finish=at+round(s['duration_ms']*48)
                left=max(start,at);right=min(start+count,finish)
                if right<=left:continue
                with wave.open(str(store.root()/'dubbing-cache'/f"{s['cache_key']}.wav"),'rb') as audio:
                    audio.setpos(left-at);data=audio.readframes(right-left)
                pos=(left-start)*2;block=block[:pos]+pcm_add(block[pos:pos+len(data)],data)+block[pos+len(data):]
            out.writeframesraw(block)

def execute(job,command):
    job['_deadline']=time.monotonic()+10800
    payload=json.loads(job['payload']);directory=store.root()/'dubbing-staging'/job['id'];directory.mkdir(parents=True,exist_ok=True)
    if shutil.disk_usage(directory).free<130*1024**2:raise ProviderError('Không đủ dung lượng đĩa dự phòng để xử lý giọng.')
    if job['kind']=='voice_extract':
        path=directory/'reference.wav'
        command([os.getenv('DUBISUB_FFMPEG','ffmpeg'),'-v','error','-nostdin','-ss',str(payload['start_ms']/1000),'-t',str((payload['end_ms']-payload['start_ms'])/1000),'-protocol_whitelist','file,pipe','-format_whitelist','mov,matroska,webm,avi,mp3,wav,flac,ogg,mpegts,mpeg,aac','-i',job['path'],'-map',f"0:a:{payload['audio_stream']}",'-vn','-ac','1','-ar','48000','-af','loudnorm=I=-20:TP=-2:LRA=7','-c:a','pcm_s16le','-y',str(path)],job)
        with wave.open(str(path),'rb') as audio:
            duration=audio.getnframes()/audio.getframerate()
            if not 2.99<=duration<=8.01:raise ProviderError('Đoạn audio thực tế không đủ 3–8 giây.')
            if pcm_rms(audio.readframes(audio.getnframes()))<100:raise ProviderError('Mẫu quá nhỏ hoặc im lặng; chọn lại đoạn có giọng rõ.')
        final=store.root()/'voice-profiles'/f"{payload['profile_id']}.wav";final.parent.mkdir(exist_ok=True)
        try:
            with store.connect() as db:
                db.execute('BEGIN IMMEDIATE');active(job);doc=store.project(db,job['project_id']);path.replace(final)
                doc.setdefault('voice_profiles',{})[payload['profile_id']]={k:payload[k] for k in ('name','asset_id','start_ms','end_ms','permission_confirmed','clean_sample_confirmed')}
                doc['voice_profiles'][payload['profile_id']].update(sample_rate=48000,language='vi',created_at=time.time(),checksum=hashlib.sha256(final.read_bytes()).hexdigest())
                store.save(db,doc);db.execute("UPDATE jobs SET state='succeeded',progress=100,error=NULL WHERE id=?",(job['id'],))
        except BaseException:
            final.unlink(missing_ok=True);raise
        return
    with store.connect() as db:
        current=store.project(db,job['project_id'])
    if any(pid not in current.get('voice_profiles',{}) for pid in payload['profiles']):raise ProviderError('Hồ sơ giọng đã bị xóa; không thể thử lại tác vụ dùng hồ sơ đó.')
    if payload.get('analysis_id'):
        from .analysis import source_current
        analysis=current.get('analyses',{}).get(payload['analysis_id'])
        if fingerprint(analysis)!=payload['review_hash'] or not source_current(current,analysis):raise ProviderError('Kịch bản/transcript đã đổi; tạo tác vụ lời dẫn mới để giữ phiên bản đúng.')
    provider=payload['provider'];capability(provider);registered={};segments=[]
    timings={'tts_seconds':0.,'tts_requests':0,'tts_cache_hits':0}
    cache=store.root()/'dubbing-cache';cache.mkdir(exist_ok=True)
    preset_ids={v['id'] for v in catalog(provider) if 'vi' in v['languages']}
    for index,cue in enumerate(payload['cues']):
        active(job);speaker=payload['cue_speakers'].get(cue['id']);voice=payload['speakers'].get(speaker,payload['voice'])
        profile_id=voice['id'] if voice['kind']=='profile' else None
        signature={'project_id':job['project_id'],'text':cue['text'],'voice':voice,'provider':provider,'profile':payload['profiles'].get(profile_id),'settings':{'format':'pcm16','sample_rate':48000}}
        key=fingerprint(signature);final=cache/f'{key}.wav'
        if not final.exists():
            tts_started=time.perf_counter()
            if profile_id:
                if profile_id not in registered:registered[profile_id]=register(provider,profile_id)
                voice_id=registered[profile_id]
            else:
                if voice['id'] not in preset_ids:raise ProviderError('Giọng preset không tồn tại. Không đổi giọng ngầm.')
                voice_id=voice['id']
            generated=synthesize(job,command,provider,voice_id,cue['text'],directory);active(job);generated.replace(final)
            timings['tts_requests']+=1;timings['tts_seconds']+=time.perf_counter()-tts_started
        else:timings['tts_cache_hits']+=1
        with wave.open(str(final),'rb') as audio:duration_ms=round(audio.getnframes()/audio.getframerate()*1000)
        speed_factor=1.;slot_end=cue['end_ms']
        if payload.get('fit_timing'):
            slot_end=payload['cues'][index+1]['start_ms']-80 if index+1<len(payload['cues']) else payload.get('source_duration_ms') or cue['end_ms']
            available=slot_end-cue['start_ms']
            if available<=0:raise ProviderError(f'Câu {index+1} có timing chồng nhau. Sửa mốc nguồn trước khi căn giọng.')
            if duration_ms>available:
                speed_factor=duration_ms/available*1.02
                if speed_factor>2:raise ProviderError(f'Câu {index+1} không đủ khoảng trống ngay cả ở tốc độ 2x. Tách/sửa câu; không cắt mất lời hoặc chồng tiếng.')
                fit_key=fingerprint({'raw_cache_key':key,'available_ms':available,'alignment_version':1})
                fitted=cache/f'{fit_key}.wav'
                if not fitted.exists():
                    temp=directory/f'fit-{index}.wav'
                    command([os.getenv('DUBISUB_FFMPEG','ffmpeg'),'-v','error','-nostdin','-i',str(final),'-af',f'atempo={speed_factor}','-ac','1','-ar','48000','-c:a','pcm_s16le','-y',str(temp)],job)
                    active(job);temp.replace(fitted)
                final=fitted;key=fit_key
                with wave.open(str(final),'rb') as audio:duration_ms=round(audio.getnframes()/audio.getframerate()*1000)
                if duration_ms>available+40:raise ProviderError('Không căn được độ dài giọng trong khoảng trống; cần sửa câu.')
        item={**cue,'cache_key':key,'duration_ms':duration_ms,'overflow_ms':max(0,duration_ms-(cue['end_ms']-cue['start_ms'])),'speaker':speaker or 'default','voice':voice,'profile_id':profile_id,'overlap':False}
        if payload.get('analysis_id'):
            output_start=segments[-1]['output_end_ms'] if segments else 0
            item.update(start_ms=output_start,end_ms=output_start+duration_ms,output_end_ms=output_start+math.ceil(duration_ms/40)*40,overflow_ms=0)
        segments.append(item)
        item.update(speed_factor=speed_factor,slot_end_ms=slot_end)
        if payload.get('fit_timing'):item['overflow_ms']=max(0,cue['start_ms']+duration_ms-slot_end)
        try:
            with store.connect() as db:
                db.execute('BEGIN IMMEDIATE');active(job);doc=store.project(db,job['project_id']);doc.setdefault('dubbing_cache',{})[key]={'profile_id':profile_id};store.save(db,doc)
                db.execute("UPDATE jobs SET checkpoint=?,progress=? WHERE id=? AND owner=? AND state='running'",(json.dumps({'segments':segments,'metrics':timings}),int(10+70*(index+1)/len(payload['cues'])),job['id'],job['owner']))
        except BaseException:
            final.unlink(missing_ok=True);raise
    for i,s in enumerate(segments):
        s['overlap']=any(i!=j and s['start_ms']<t['start_ms']+t['duration_ms'] and t['start_ms']<s['start_ms']+s['duration_ms'] for j,t in enumerate(segments))
    def phase(name,progress):
        with store.connect() as db:
            active(job)
            db.execute("UPDATE jobs SET checkpoint=?,progress=? WHERE id=? AND owner=? AND state='running'",(json.dumps({'segments':segments,'metrics':timings,'phase':name}),progress,job['id'],job['owner']))
    phase('mix',82)
    mix_started=time.perf_counter()
    dry=directory/'voice.wav';mix(segments,dry,job)
    output=directory/'narration.wav'
    from .audio_mix import render as render_mix
    expected=max(payload.get('source_duration_ms',0),max(s['start_ms']+s['duration_ms'] for s in segments)) if not payload.get('analysis_id') else segments[-1]['output_end_ms']
    bed=store.root()/'stems'/f'{payload["stem_id"]}-background.wav' if payload.get('stem_id') else job.get('path')
    original_voice=store.root()/'stems'/f'{payload["stem_id"]}-vocals.wav' if payload.get('stem_id') else None
    if payload.get('analysis_id') and payload.get('audio_mix',{}).get('mode','replace')!='replace':
        from .review_mapping import mix_audio
        mix_audio(job,command,segments,dry,output,directory,payload,bed,original_voice)
    else:render_mix(bed,dry,output,payload.get('audio_mix',{}),expected,job,command,original_voice)
    timings['mix_seconds']=time.perf_counter()-mix_started;render_started=time.perf_counter()
    phase('render' if payload['export_video'] else 'validate',88)
    subtitle_cues=[{'id':s['id'],'text':s['text'],'start_ms':s['start_ms'],'end_ms':s['start_ms']+s['duration_ms']} for s in segments]
    video=directory/'narration.mp4'
    if payload['export_video'] and payload.get('analysis_id'):
        from .review_render import render
        render(job,command,segments,output,video,directory,payload['source_duration_ms'],payload)
    elif payload['export_video']:
        video_cap=min(int(os.getenv('DUBISUB_MAX_UPLOAD_MB','2048'))*1024**2,shutil.disk_usage(directory).free-128*1024**2)
        if video_cap<=0:raise ProviderError('Không đủ đĩa để xuất MP4.')
        from .rendering import normalize_plan,video_filter_args
        raw_plan={'fps':30}
        if payload.get('subtitle_mask'):raw_plan['subtitle_mask']=payload['subtitle_mask']
        plan=normalize_plan(raw_plan,payload['source_duration_ms'])
        plan.update(source_width=payload.get('source_width'),source_height=payload.get('source_height'))
        video_args=video_filter_args(plan,subtitle_cues,directory,payload.get('burn_subtitles',False))
        expected=max(payload.get('source_duration_ms',0),max(s['start_ms']+s['duration_ms'] for s in segments))
        command([os.getenv('DUBISUB_FFMPEG','ffmpeg'),'-v','error','-nostdin','-protocol_whitelist','file,pipe','-format_whitelist','mov,matroska,webm,avi,mp3,wav,flac,ogg,mpegts,mpeg,aac','-i',job['path'],'-i',str(output),*video_args,'-map','1:a:0','-af',f'apad=whole_dur={expected/1000}','-c:v','libx264','-preset','veryfast','-threads','2','-pix_fmt','yuv420p','-c:a','aac','-movflags','+faststart','-fs',str(video_cap),'-y',str(video)],job,timeout=10800,cwd=directory)
        probe=json.loads(command([os.getenv('DUBISUB_FFPROBE','ffprobe'),'-v','error','-show_format','-of','json',str(video)],job))
        expected=max(payload.get('source_duration_ms',0),max(s['start_ms']+s['duration_ms'] for s in segments))
        if abs(float(probe.get('format',{}).get('duration',0))*1000-expected)>200:raise ProviderError('Video xuất thiếu thời lượng hoặc chạm giới hạn file; không lưu bản chưa hoàn tất.')
    destination=store.root()/'dubbings';destination.mkdir(exist_ok=True)
    timings['render_seconds']=time.perf_counter()-render_started
    phase('validate',97)
    moved=[]
    try:
        with store.connect() as db:
            db.execute('BEGIN IMMEDIATE');active(job);doc=store.project(db,job['project_id'])
            if payload.get('analysis_id') and (fingerprint(doc.get('analyses',{}).get(payload['analysis_id']))!=payload['review_hash'] or not source_current(doc,doc.get('analyses',{}).get(payload['analysis_id']))):raise ProviderError('Kịch bản/transcript đã đổi trong khi tạo lời dẫn; chưa lưu kết quả lỗi thời.')
            for ext,path in [('wav',output),('voice.wav',dry),('mp4',video)]:
                if path.exists():
                    target=destination/f"{job['id']}.{ext}";path.replace(target);moved.append(target)
            item={'id':job['id'],'track_id':payload['track_id'],'source_revision':payload['source_revision'],'segments':segments,'subtitle_cues':subtitle_cues,'fit_timing':payload.get('fit_timing',False),'burn_subtitles':payload.get('burn_subtitles',False),'profile_ids':list(payload['profiles']),'video':payload['export_video'],'created_at':time.time()}
            item['audio_mix']=payload.get('audio_mix',{});item['dry_voice']=True
            item['timings']=timings
            if payload.get('analysis_id'):
                tid=store.uid();item.update(track_id=tid,analysis_id=payload['analysis_id'])
                doc['tracks'].append({'id':tid,'asset_id':job['asset_id'],'kind':'review','language':payload['language'],'reviewed':True,'analysis_id':payload['analysis_id'],'job_id':job['id'],'cues':[{'id':s['id'],'text':s['text'],'start_ms':s['start_ms'],'end_ms':s['end_ms']} for s in segments]})
            doc.setdefault('dubbings',[]).append(item);store.save(db,doc);db.execute("UPDATE jobs SET state='succeeded',progress=100,error=NULL WHERE id=?",(job['id'],))
    except BaseException:
        for path in moved:path.unlink(missing_ok=True)
        raise
