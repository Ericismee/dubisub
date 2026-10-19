import subprocess
import wave
import numpy as np
import pytest
from backend.audio_mix import render,normalize


def command(args,job,**kwargs):
    return subprocess.run(args,capture_output=True,check=True,timeout=30).stdout.decode()


def test_stereo_background_survives_speech_gaps_and_ducks(tmp_path):
    source=tmp_path/'music.wav';voice=tmp_path/'voice.wav'
    rate=48000;t=np.arange(3*rate)/rate
    bed=np.stack([np.sin(t*2*np.pi*440),np.sin(t*2*np.pi*880)],axis=1)*.18
    speech=np.sin(t*2*np.pi*1300)*.4*((t>=1)&(t<2))
    for path,data,channels in [(source,bed,2),(voice,speech,1)]:
        with wave.open(str(path),'wb') as w:
            w.setnchannels(channels);w.setsampwidth(2);w.setframerate(rate);w.writeframes((data*32767).astype('<i2').tobytes())
    outputs=[]
    for ducking in [False,True]:
        out=tmp_path/f'mix-{ducking}.wav';render(source,voice,out,{'mode':'voiceover','source_volume':1,'ducking':ducking},3000,{},command)
        with wave.open(str(out)) as w:
            assert w.getnchannels()==2 and w.getnframes()==3*rate
            audio=np.frombuffer(w.readframes(w.getnframes()),dtype='<i2').reshape(-1,2)/32768
        assert np.max(np.abs(audio))<.96
        assert np.sqrt(np.mean(audio[int(.2*rate):int(.7*rate)]**2))>.1
        assert np.sqrt(np.mean(audio[int(2.5*rate):int(2.9*rate)]**2))>.1
        assert not np.allclose(audio[:,0],audio[:,1])
        # Measure the original music frequency during narration, not total RMS.
        section=audio[int(1.4*rate):int(1.8*rate),0]
        outputs.append(abs(np.mean(section*np.exp(-2j*np.pi*440*np.arange(len(section))/rate))))
    assert outputs[1]<outputs[0]*.7


def test_mix_rejects_unsafe_or_ambiguous_inputs():
    for raw in [{'source_volume':float('nan')},{'voice_volume':-1},{'mode':'fake-music-stem'},{'audio_stream':True}]:
        with pytest.raises(ValueError):normalize(raw)
