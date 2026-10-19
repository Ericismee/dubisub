"""Materialize this project's HF snapshot files for ONNX external-data security.

Only existing symlinks whose targets stay inside the isolated runtime are copied.
No downloads, global cache changes or relaxed ONNX security settings.
"""
import os
import shutil
import tempfile
from pathlib import Path


def main():
    root=(Path(__file__).resolve().parents[1]/'data/vieneu-runtime').resolve()
    hub=root/'huggingface/hub'
    count=0
    for snapshot in hub.glob('models--*/snapshots/*'):
        for path in snapshot.rglob('*'):
            if not path.is_symlink():continue
            target=path.resolve(strict=True)
            if not target.is_relative_to(root) or not target.is_file():
                raise RuntimeError('Model link escapes the isolated VieNeu runtime.')
            if shutil.disk_usage(root).free<target.stat().st_size+128*1024**2:
                raise RuntimeError('Not enough disk space to materialize model weights.')
            fd,name=tempfile.mkstemp(prefix='.onnx-copy-',dir=path.parent)
            os.close(fd)
            try:
                shutil.copyfile(target,name)
                os.replace(name,path)
            finally:
                Path(name).unlink(missing_ok=True)
            count+=1
    print(f'VieNeu: materialized {count} local model links.')


if __name__=='__main__':main()
