import subprocess
from backend.review_scenes import detect, select_ranges, select_shots


def test_evidence_ranges_keep_order_merge_overlap_and_split_shots():
    rows=select_ranges([{'start_ms':4000,'end_ms':6000},
                        {'start_ms':1000,'end_ms':3000},
                        {'start_ms':2000,'end_ms':3500}], [0,2500,5000,8000],8000)
    assert rows==[{'start_ms':1000,'end_ms':2500},{'start_ms':2500,'end_ms':3500},
                  {'start_ms':4000,'end_ms':5000},{'start_ms':5000,'end_ms':6000}]


def test_actual_ffmpeg_detects_hard_cut(tmp_path):
    video=tmp_path/'cuts.mp4'
    subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','color=black:s=320x180:d=2',
                    '-f','lavfi','-i','color=white:s=320x180:d=2','-filter_complex',
                    '[0:v][1:v]concat=n=2:v=1:a=0','-y',str(video)],check=True)
    def command(args,job,**kwargs):
        return subprocess.run(args,capture_output=True,text=True,check=True,timeout=30).stdout
    boundaries=detect({'path':str(video)},command,4000)
    assert boundaries[0]==0 and boundaries[-1]==4000
    assert any(abs(p-2000)<=500 for p in boundaries[1:-1])


def test_short_narration_selects_readable_shots_from_every_citation():
    selected,skipped=select_shots([{'start_ms':0,'end_ms':20000},{'start_ms':30000,'end_ms':40000}],list(range(0,41000,500)),40000,6000)
    assert len(selected)==7 and skipped==53
    assert selected==sorted(selected,key=lambda r:r['start_ms'])
    assert any(r['start_ms']>=30000 for r in selected)
    assert any(r['end_ms']<=20000 for r in selected)
