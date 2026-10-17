"""Test-only worker: allow exactly the owned loopback HTTP fixture origin.

Production backend.worker has no CLI/env switch to enable private network access.
"""
import sys
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend import store, worker, link_tasks
from backend.safe_http import SafeHTTP

if __name__=='__main__':
    port=int(sys.argv[1])
    origin=('http','127.0.0.1',port)
    store.migrate()
    while True:
        if not worker.run_once(link_executor=lambda jid:link_tasks.execute(jid,SafeHTTP(test_origin=origin))):
            time.sleep(.15)
