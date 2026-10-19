"""Offline, CPU-only trial of a single pinned public Demucs model via audio-separator.

Music-trained baseline, NOT a claim of clean film-dialogue separation.
"""
import contextlib
import hashlib
import json
import logging
import os
from pathlib import Path
import sys
import time
from fractions import Fraction

os.environ['CUDA_VISIBLE_DEVICES']='-1'
os.environ['OMP_NUM_THREADS']='2'
os.environ['MKL_NUM_THREADS']='2'
EXPECTED='8726e21a993978c7ba086d3872e7608d7d5bfca646ca4aca459ffda844faa8b4'


def main():
    request=json.load(open(sys.argv[1],encoding='utf-8'));directory=Path(request['output_dir']).resolve();directory.mkdir(parents=True,exist_ok=True)
    model_dir=Path(os.getenv('DUBISUB_DATA_DIR',Path(__file__).resolve().parents[1]/'data')).resolve()/'separator-runtime/models';weight=model_dir/'955717e8-8726e21a.th'
    if hashlib.file_digest(weight.open('rb'),'sha256').hexdigest()!=EXPECTED:raise ValueError('Separation model checksum changed; not loading it.')
    started=time.perf_counter()
    with contextlib.redirect_stdout(sys.stderr):
        import torch
        import numpy as np
        import requests
        import urllib.request
        from audio_separator.separator import Separator
        torch.set_num_threads(2);torch.set_num_interop_threads(1)
        # No model/metadata downloads or media transfer during a processing job.
        def offline(*args,**kwargs):raise RuntimeError('Separation worker is offline. Install pinned model before processing.')
        requests.sessions.Session.request=offline;urllib.request.urlopen=offline;torch.hub.download_url_to_file=offline
        separator=Separator(model_file_dir=str(model_dir),output_dir=str(directory),output_format='WAV',use_soundfile=True,normalization_threshold=1.,log_level=logging.WARNING,demucs_params={'segment_size':5,'shifts':0,'overlap':.25,'segments_enabled':True})
        separator.list_supported_model_files=lambda:{'Demucs':{'Demucs htdemucs pinned':{'filename':'htdemucs.yaml','download_files':['955717e8-8726e21a.th','htdemucs.yaml']}}}
        separator.load_model('htdemucs.yaml')
        from audio_separator.separator.uvr_lib_v5.demucs.htdemucs import HTDemucs
        from audio_separator.separator.uvr_lib_v5.demucs.hdemucs import HDemucs
        original_load=torch.load
        def safe_load(path,*args,**kwargs):
            if Path(path).resolve()!=weight.resolve():raise ValueError('Unregistered checkpoint path.')
            kwargs['weights_only']=True
            allowed=[(HTDemucs,'demucs.htdemucs.HTDemucs'),(HDemucs,'demucs.hdemucs.HDemucs'),Fraction,np.dtype,(np._core.multiarray.scalar,'numpy.core.multiarray.scalar'),np.dtypes.Float64DType,np.dtypes.Float32DType]
            with torch.serialization.safe_globals(allowed):return original_load(path,*args,**kwargs)
        torch.load=safe_load
        outputs=separator.separate(request['input'],custom_output_names={'Vocals':'vocals','Drums':'drums','Bass':'bass','Other':'other'})
    files={}
    for name in outputs:
        path=(directory/name).resolve()
        if not path.is_relative_to(directory) or not path.is_file():raise ValueError('Separator output outside staging.')
        for kind in ('vocals','drums','bass','other'):
            if kind in path.stem.lower():files[kind]=str(path)
    if set(files)!={'vocals','drums','bass','other'}:raise ValueError('Separator did not produce all real stems.')
    print(json.dumps({'files':files,'elapsed_seconds':time.perf_counter()-started,'model':'htdemucs','model_sha256':EXPECTED,'device':'cpu','limitations':'Music-trained baseline. Background is combined non-vocal stems; may lose SFX or retain dialogue. Review real sample before whole-film use.'}))


if __name__=='__main__':main()
