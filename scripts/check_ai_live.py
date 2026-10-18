"""Explicit live Ollama smoke using only generated, permitted test content.

No ASR or subjective AI-quality claim. Never reads the user's projects or keys.
"""
import argparse
import base64
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from backend.app import app
from backend import worker
from backend.providers import chat_json,request,ollama_config
from backend.capabilities import infer,record

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--endpoint',default='http://127.0.0.1:11434')
    parser.add_argument('--llm-model',required=True)
    parser.add_argument('--vision-model')
    args=parser.parse_args()
    llm={'kind':'translation','protocol':'ollama','endpoint':args.endpoint,'model':args.llm_model,'key_env':''}
    vision={**llm,'kind':'vision','model':args.vision_model}
    print('Live provider receives only generated transcript/frame data: '+args.endpoint,flush=True)
    with tempfile.TemporaryDirectory(prefix='dubisub-live-ai-') as folder:
        os.environ['DUBISUB_DATA_DIR']=str(Path(folder)/'data')
        with TestClient(app) as client:
            client.put('/api/settings',json={'providers':[llm]+([vision] if args.vision_model else [])})
            infer(llm,'text');record(llm,'text','actual_nonce_inference')
            pid=client.post('/api/projects',json={'name':'Permitted live AI smoke'}).json()['id']
            sub='1\n00:00:00,100 --> 00:00:01,500\nWelcome to our video studio.\n\n2\n00:00:01,600 --> 00:00:03,000\nWe translate subtitles and preserve the original media.\n'
            client.post(f'/api/projects/{pid}/upload',data={'kind':'subtitle'},files={'file':('permitted-script.srt',sub.encode())})
            def run(**options):
                p=client.get('/api/projects/'+pid).json();body={'revision':p['revision'],'track_id':p['tracks'][0]['id'],**options}
                plan=client.post(f'/api/projects/{pid}/auto/plan',json=body).json();assert not plan['blockers'],plan
                r=client.post(f'/api/projects/{pid}/auto',json={**body,'confirmed':True,'consent_signature':plan['signature']});assert r.status_code==202,r.text
                for _ in range(12):
                    worker.run_once();result=client.get(f'/api/projects/{pid}/auto').json()[0]
                    if result['state']!='running':break
                assert result['state'] in ('draft','succeeded'),result
                return client.get('/api/projects/'+pid).json()
            p=run(output='subtitles');out=Path('test-results');out.mkdir(exist_ok=True)
            translated=p['tracks'][-1];assert [c['id'] for c in translated['cues']]==[c['id'] for c in p['tracks'][0]['cues']]
            (out/'ollama-translation-live.json').write_text(json.dumps(translated,ensure_ascii=False,indent=2),encoding='utf-8')
            print('PASS: actual LLM translation with preserved IDs and SRT/VTT/ASS exports',flush=True)
            if not args.vision_model:return
            details=request(ollama_config(vision),'api/show',body={'model':args.vision_model})
            assert 'vision' in details.get('capabilities',[]),'Model does not declare image input'
            image=Path(folder)/'rgb.jpg'
            subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=c=red:s=600x200:d=0.1','-vf','drawbox=x=200:y=0:w=200:h=200:color=blue:t=fill,drawbox=x=400:y=0:w=200:h=200:color=green:t=fill','-frames:v','1','-y',str(image)],check=True)
            answer=chat_json(vision,[{'role':'user','content':'Inspect this image of three colored rectangles. Return exactly JSON with one key colors and a list of the three color names from left to right, in lowercase English.'}],images=[base64.b64encode(image.read_bytes()).decode()])
            assert answer=={'colors':['red','blue','green']},'Image calibration failed; do not claim verified vision'
            record(vision,'image','declared_vision_and_actual_rgb_image_inference')
            media=Path(folder)/'pattern.mp4'
            subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=c=blue:s=320x180:d=4','-vf','drawbox=x=40:y=40:w=80:h=80:color=red:t=fill','-c:v','libx264','-y',str(media)],check=True)
            with media.open('rb') as f:client.post(f'/api/projects/{pid}/upload',data={'kind':'media'},files={'file':('permitted-pattern.mp4',f)})
            worker.run_once();p=client.get('/api/projects/'+pid).json();aid=next(a['id'] for a in p['assets'] if a['kind']=='media')
            p=run(asset_id=aid,mode='summary',use_vision=True,output='draft')
            (out/'ollama-vision-summary-live.json').write_text(json.dumps(p['analyses'],ensure_ascii=False,indent=2),encoding='utf-8')
            print('PASS: actual sampled frame + transcript → evidence-linked summary draft',flush=True)
            print(json.dumps({a['kind']:{'scope':a['scope'],'items':len(a['items'])} for a in p['analyses'].values()}),flush=True)

if __name__=='__main__':main()
