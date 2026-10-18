"""Explicit OpenAI-compatible HTTP adapter; no model/key/voices are assumed."""
import json
import os
from urllib.parse import urlsplit

import httpx
from . import store


class ProviderError(ValueError):
    pass

DEFAULT_TTS={'kind':'tts','protocol':'openai','endpoint':'http://127.0.0.1:8001/v1','model':'vieneu-v3-turbo','key_env':''}


def configured(kind, *, require_model=True):
    with store.connect() as db:
        row=db.execute('SELECT providers FROM settings WHERE id=1').fetchone()
    providers=json.loads(row[0]) if row else []
    selected=next((p for p in providers if p['kind']==kind),None)
    if not selected and kind=='tts':selected=dict(DEFAULT_TTS)
    if not selected or (require_model and not selected.get('model')):
        label={'asr':'ASR (Whisper/faster-whisper hoặc API nhận dạng)','translation':'Dịch thuật (Ollama hoặc LLM OpenAI-compatible)','tts':'Giọng đọc (TTS)'}[kind]
        raise ProviderError(f'Chưa cấu hình {label}. Mở Cài đặt → nhóm tương ứng. VieNeu chỉ tạo giọng, không nhận dạng hay dịch phụ đề.')
    if kind!='tts' and 'vieneu' in selected.get('model','').lower():
        raise ProviderError('VieNeu chỉ dùng cho Giọng đọc (TTS). Dịch thuật cần Ollama/LLM; ASR cần Whisper hoặc provider nhận dạng. Hãy sửa đúng nhóm trong Cài đặt.')
    if selected.get('key_env') and not os.getenv(selected['key_env']):
        raise ProviderError('Chưa tìm thấy biến môi trường khóa đã chọn trong tiến trình xử lý.')
    return selected


def request(config, path, *, body=None, files=None, data=None, max_bytes=8*1024**2, timeout=120):
    parts=urlsplit(config['endpoint'])
    if parts.scheme not in ('http','https') or not parts.hostname or parts.username or parts.query or parts.fragment:
        raise ProviderError('Endpoint provider không hợp lệ.')
    headers={'Accept':'application/json'}
    if config.get('key_env'):
        secret=os.getenv(config['key_env'])
        if not secret:raise ProviderError('Worker chưa có biến môi trường khóa đã cấu hình.')
        headers['Authorization']='Bearer '+secret
    try:
        with httpx.Client(trust_env=False,follow_redirects=False,timeout=httpx.Timeout(timeout,connect=min(10,timeout))) as client:
            with client.stream('GET' if body is None and files is None else 'POST',config['endpoint'].rstrip('/')+'/'+path.lstrip('/'),headers=headers,json=body,files=files,data=data) as response:
                if response.status_code in (401,403):raise ProviderError('Provider từ chối xác thực. Kiểm tra quyền truy cập và khóa.')
                if response.status_code==429:raise ProviderError('Provider đang giới hạn lượt gọi. Hãy thử lại sau.')
                if response.status_code>=300:raise ProviderError(f'Provider trả HTTP {response.status_code}; kiểm tra endpoint/model tương thích.')
                content=bytearray()
                for chunk in response.iter_bytes(65536):
                    content.extend(chunk)
                    if len(content)>max_bytes:raise ProviderError('Phản hồi provider vượt giới hạn cho phép.')
        try:return json.loads(content)
        except (ValueError,UnicodeError):raise ProviderError('Provider không trả JSON hợp lệ.') from None
    except httpx.HTTPError:
        raise ProviderError('Không kết nối được provider hoặc đã hết thời gian chờ.') from None


def check_models(config):
    if config.get('protocol')=='ollama':
        data=request(ollama_config(config),'api/tags',timeout=10)
        if not isinstance(data,dict) or not isinstance(data.get('models'),list):
            raise ProviderError('Ollama không trả danh sách model đã cài.')
        models=[m['name'] for m in data['models'] if isinstance(m,dict) and isinstance(m.get('name'),str) and len(m['name'])<=200][:300]
        return {'connected':True,'models':models,'configured_model_available':config.get('model') in models,'capabilities':['model_listing'],'inference_verified':False}
    data=request(config,'models',timeout=10)
    if not isinstance(data,dict) or not isinstance(data.get('data'),list):
        raise ProviderError('Provider không trả danh sách model tương thích.')
    models=[m['id'] for m in data['data'] if isinstance(m,dict) and isinstance(m.get('id'),str) and len(m['id'])<=200][:300]
    return {'connected':True,'models':models,'configured_model_available':config.get('model') in models,
            'capabilities':['model_listing'],'inference_verified':False}


def ollama_config(config):
    result=dict(config)
    endpoint=result['endpoint'].rstrip('/')
    for suffix in ('/api','/v1'):
        if endpoint.endswith(suffix):endpoint=endpoint[:-len(suffix)];break
    result['endpoint']=endpoint
    return result


def chat_json(config, messages):
    if config.get('protocol')=='ollama':
        response=request(ollama_config(config),'api/chat',body={'model':config['model'],'messages':messages,'stream':False,'format':'json','options':{'temperature':0.1,'num_predict':4096}})
        try:return json.loads(response['message']['content'])
        except (KeyError,TypeError,ValueError):raise ProviderError('Ollama không trả chat/JSON hợp lệ.') from None
    response=request(config,'chat/completions',body={'model':config['model'],'messages':messages,'temperature':0.1,'max_tokens':4096,'response_format':{'type':'json_object'}})
    try:return json.loads(response['choices'][0]['message']['content'])
    except (KeyError,TypeError,IndexError,ValueError):raise ProviderError('Provider không trả cấu trúc chat/JSON hợp lệ.') from None


# Suggestions only: installation, hardware suitability and translation quality are not inferred.
MODEL_FAMILIES=('llama3.1','llama3.2','llama3','llama3.3','qwen2.5','qwen3','qwen3.5','gemma3','gemma2','gemma4','mistral','mistral-nemo','mistral-small','mistral-small3.2','phi3','phi4','deepseek-r1','gpt-oss','qwen2','tinyllama','smollm2','olmo2','mixtral','falcon3')
