"""Install public model weights in DubiSub storage, without credentials or remote code."""
import argparse
import json
import os
import shutil
import sys
import re
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import httpx
from backend.local_asr import MODELS,model_path,ready

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--model',choices=MODELS,default='small');args=parser.parse_args()
    if ready(args.model):print('Model đã cài, giữ nguyên revision và file đang dùng.');return
    root=model_path(args.model);root.mkdir(parents=True,exist_ok=True)
    if shutil.disk_usage(root).free<2*1024**3:raise RuntimeError('Cần tối thiểu 2 GiB đĩa trống để cài model.')
    with httpx.Client(trust_env=False,follow_redirects=True,timeout=httpx.Timeout(60,connect=15)) as client:
        response=client.get('https://huggingface.co/api/models/'+MODELS[args.model]);response.raise_for_status();revision=response.json()['sha']
        if not re.fullmatch('[0-9a-f]{40}',revision):raise RuntimeError('Revision model không hợp lệ.')
        files=[f['rfilename'] for f in response.json()['siblings'] if f['rfilename'] in ('model.bin','config.json','tokenizer.json','vocabulary.txt','vocabulary.json','preprocessor_config.json')]
        total=0
        for filename in files:
            target=root/filename;partial=root/(filename+'.part')
            try:
                with client.stream('GET',f'https://huggingface.co/{MODELS[args.model]}/resolve/{revision}/{filename}') as stream:
                    stream.raise_for_status();size=0
                    with partial.open('wb') as output:
                        for chunk in stream.iter_bytes(1024**2):
                            size+=len(chunk);total+=len(chunk)
                            if total>1024**3 or shutil.disk_usage(root).free<128*1024**2:raise RuntimeError('Model vượt giới hạn 1 GiB hoặc thiếu đĩa.')
                            output.write(chunk)
                partial.replace(target);print(filename+': '+str(size)+' bytes',flush=True)
            finally:partial.unlink(missing_ok=True)
        (root/'source.json').write_text(json.dumps({'repo':MODELS[args.model],'revision':revision}),encoding='utf-8')
        print('Installed '+args.model+' at '+str(root),flush=True)

if __name__=='__main__':
    try:main()
    except httpx.HTTPError:raise SystemExit('Không tải được model. Kiểm tra mạng rồi chạy lại; không ghi URL/token chuyển hướng vào log.') from None
