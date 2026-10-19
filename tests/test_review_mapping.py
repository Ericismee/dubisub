import subprocess
import wave
from array import array
import math
import pytest
from backend.review_mapping import approved,source_audio
from backend.providers import ProviderError


def test_approved_mapping_never_invents_footage():
    segment={'start_ms':0,'output_end_ms':2000,'source_ranges':[{'start_ms':1000,'end_ms':1800},{'start_ms':4000,'end_ms':4800}]}
    with pytest.raises(ProviderError,match='Thiếu hình'):approved(segment,5000)
    mapping=approved(segment,5000,True)
    assert sum(r['output_duration_ms'] for r in mapping)==2000
    assert mapping[1]['output_start_ms']==mapping[0]['output_duration_ms']
    assert all(r['end_ms']<=4800 for r in mapping)


def test_review_source_audio_uses_same_ranges(tmp_path):
    source=tmp_path/'source.wav'
    subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','sine=frequency=440:duration=1','-f','lavfi','-i','sine=frequency=880:duration=1','-filter_complex','[0:a][1:a]concat=n=2:v=0:a=1[out]','-map','[out]','-y',str(source)],check=True)
    segment={'start_ms':0,'output_end_ms':800,'source_ranges':[{'start_ms':1000,'end_ms':1800}]}
    mapping=approved(segment,2000)
    destination=tmp_path/'bed.wav'
    def command(args,job,**kwargs):return subprocess.check_output(args,**kwargs).decode()
    source_audio(source,mapping,destination,tmp_path,{},command)
    with wave.open(str(destination)) as wav:
        assert wav.getnchannels()==2 and wav.getframerate()==48000
        assert wav.getnframes()==38400
        samples=array('h',wav.readframes(wav.getnframes()))[::2]
    def strength(hz):return abs(sum(x*complex(math.cos(2*math.pi*hz*i/48000),math.sin(2*math.pi*hz*i/48000)) for i,x in enumerate(samples)))
    assert strength(880)>strength(440)*100
