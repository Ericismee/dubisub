"""Live offline Whisper + local Ollama + FFmpeg subtitle smoke, generated content only."""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from fastapi.testclient import TestClient
from backend.app import app
from backend import worker
from backend.local_asr import DEFAULT
from backend.capabilities import infer,record

def main():
    os.environ['DUBISUB_ASR_MODEL_DIR']=str(ROOT/'data'/'asr-models')
    with tempfile.TemporaryDirectory(prefix='dubisub-live-asr-') as folder:
        work=Path(folder);os.environ['DUBISUB_DATA_DIR']=str(work/'db')
        speech=work/'generate.ps1';audio=work/'permitted-speech.wav';media=work/'permitted-video.mp4'
        speech.write_text("param([string]$OutputPath)\nAdd-Type -AssemblyName System.Speech\n$taskVoice=New-Object System.Speech.Synthesis.SpeechSynthesizer\n$taskVoice.SelectVoiceByHints([System.Speech.Synthesis.VoiceGender]::Female,[System.Speech.Synthesis.VoiceAge]::Adult,0,[System.Globalization.CultureInfo]::GetCultureInfo('en-US'))\n$taskVoice.SetOutputToWaveFile($OutputPath)\n$taskVoice.Speak('Welcome to our video studio. We translate subtitles and keep the original video safe.')\n$taskVoice.Dispose()\n",encoding='utf-8')
        subprocess.run(['powershell','-NoProfile','-File',str(speech),'-OutputPath',str(audio)],check=True)
        subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','testsrc2=size=640x360:rate=24','-i',str(audio),'-c:v','libx264','-c:a','aac','-shortest','-y',str(media)],check=True)
        with TestClient(app) as client:
            llm={'kind':'translation','protocol':'ollama','endpoint':'http://127.0.0.1:11434','model':'qwen2.5:7b','key_env':''}
            client.put('/api/settings',json={'providers':[DEFAULT,llm]})
            infer(llm,'text');record(llm,'text','actual_nonce_inference')
            pid=client.post('/api/projects',json={'name':'Live permitted ASR subtitle smoke'}).json()['id']
            with media.open('rb') as f:client.post(f'/api/projects/{pid}/upload',data={'kind':'media'},files={'file':('permitted-video.mp4',f)})
            worker.run_once();p=client.get('/api/projects/'+pid).json()
            body={'revision':p['revision'],'asset_id':p['assets'][0]['id'],'source_language':'auto','targets':['vi'],'force_asr':True,'output':'video','render_plan':{'resolution':360,'subtitle_mask':{'enabled':True}}}
            plan=client.post(f'/api/projects/{pid}/auto/plan',json=body).json();assert not plan['blockers'],plan
            response=client.post(f'/api/projects/{pid}/auto',json={**body,'confirmed':True,'consent_signature':plan['signature']});assert response.status_code==202,response.text
            for _ in range(16):
                worker.run_once();result=client.get(f'/api/projects/{pid}/auto').json()[0]
                if result['state']!='running':break
            assert result['state']=='succeeded',result
            p=client.get('/api/projects/'+pid).json();asr=next(t for t in p['tracks'] if t['kind']=='asr');translated=next(t for t in p['tracks'] if t['kind']=='translation')
            assert asr['language']=='en' and asr['raw_cues'] and translated['language']=='vi'
            assert [(c['id'],c['start_ms'],c['end_ms']) for c in asr['cues']]==[(c['id'],c['start_ms'],c['end_ms']) for c in translated['cues']]
            out=ROOT/'test-results';out.mkdir(exist_ok=True)
            (out/'local-asr-live.json').write_text(json.dumps({'asr':asr,'translation':translated},ensure_ascii=False,indent=2),encoding='utf-8')
            video=client.get(f'/api/projects/{pid}/artifacts/{result["videos"][0]["id"]}');assert video.status_code==200;(out/'local-vietnamese-overlay-live.mp4').write_bytes(video.content)
            sub=client.get(f'/api/projects/{pid}/tracks/{translated["id"]}/export?format=srt');(out/'local-vietnamese-overlay-live.srt').write_text(sub.text,encoding='utf-8')
            print(json.dumps({'actual_asr_language':asr['language'],'actual_asr':[c['text'] for c in asr['cues']],'vietnamese':[c['text'] for c in translated['cues']],'video_ready':bool(result['videos'])},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
