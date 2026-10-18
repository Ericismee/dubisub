"""Offline faster-whisper adapter. Model installation is explicit, never implicit."""
import os
import json
from pathlib import Path
from . import store
from .providers import ProviderError

MODELS={'tiny':'Systran/faster-whisper-tiny','small':'Systran/faster-whisper-small'}
DEFAULT={'kind':'asr','protocol':'faster_whisper','endpoint':'http://127.0.0.1','model':'small','key_env':''}
_models={}

def model_path(name):
    if name not in MODELS:raise ProviderError('ASR local hỗ trợ tiny hoặc small đa ngôn ngữ.')
    return Path(os.environ.get('DUBISUB_ASR_MODEL_DIR',store.root()/'asr-models')).resolve()/name

def ready(name):
    path=model_path(name)
    return all((path/f).is_file() for f in ('model.bin','config.json','tokenizer.json','source.json'))

def revision(name):
    return json.loads((model_path(name)/'source.json').read_text(encoding='utf-8'))['revision']

def transcribe(path,config,language,check,progress=None):
    name=config['model']
    if not ready(name):raise ProviderError('Chưa cài model ASR local. Chạy uv run python scripts/install_asr_model.py --model '+name)
    if config.get('model_revision') and config['model_revision']!=revision(name):raise ProviderError('Model ASR đã thay revision. Tạo lượt mới; không dùng lại checkpoint của model cũ.')
    from faster_whisper import WhisperModel
    key=(name,revision(name))
    if key not in _models:_models[key]=WhisperModel(str(model_path(name)),device='cpu',compute_type='int8',cpu_threads=min(4,os.cpu_count() or 1),num_workers=1,local_files_only=True)
    check()
    segments,info=_models[key].transcribe(str(path),language=None if language=='auto' else language.split('-')[0],beam_size=5,vad_filter=True,condition_on_previous_text=False)
    rows=[]
    for segment in segments:
        check();rows.append({'start':segment.start,'end':segment.end,'text':segment.text,'avg_logprob':segment.avg_logprob,'no_speech_prob':segment.no_speech_prob})
        if progress:progress(segment.end)
        if len(rows)>5000:raise ProviderError('ASR local vượt 5000 segment trong một chunk.')
    return {'segments':rows,'language':info.language,'language_probability':info.language_probability}
