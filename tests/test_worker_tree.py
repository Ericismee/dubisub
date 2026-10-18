import csv
import io
import os
import subprocess
import sys
import threading
import time
from test_foundation import client,create
from backend import store,worker

def test_cancel_stops_owned_grandchild(client,tmp_path):
    pid=create(client)
    client.post(f'/api/projects/{pid}/upload',data={'kind':'media'},files={'file':('test.mp4',b'invalid')})
    with store.connect() as db:
        jid=db.execute('SELECT id FROM jobs').fetchone()[0]
        db.execute("UPDATE jobs SET state='running',owner=? WHERE id=?",(worker.OWNER,jid))
    file=tmp_path/'grandchild.pid';outcome=[]
    script="import subprocess,sys,time;from pathlib import Path;p=subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)']);Path(sys.argv[1]).write_text(str(p.pid));time.sleep(30)"
    def run():
        try:worker.command([sys.executable,'-c',script,str(file)],{'id':jid,'owner':worker.OWNER})
        except worker.Canceled:outcome.append('canceled')
    thread=threading.Thread(target=run);thread.start()
    try:
        deadline=time.monotonic()+10
        while not file.exists() and time.monotonic()<deadline:time.sleep(.02)
        assert file.exists()
        child=int(file.read_text())
        with store.connect() as db:db.execute("UPDATE jobs SET state='canceled' WHERE id=?",(jid,))
        thread.join(timeout=15);assert not thread.is_alive() and outcome==['canceled']
        if os.name=='nt':
            listing=subprocess.check_output(['tasklist.exe','/FI',f'PID eq {child}','/FO','CSV','/NH'],text=True)
            assert not any(len(row)>1 and row[1]==str(child) for row in csv.reader(io.StringIO(listing)))
        else:
            # A killed orphan may briefly be a zombie until init reaps it.
            path=__import__('pathlib').Path(f'/proc/{child}/stat')
            assert not path.exists() or path.read_text().split()[2]=='Z'
    finally:
        with store.connect() as db:db.execute("UPDATE jobs SET state='canceled' WHERE id=?",(jid,))
        thread.join(timeout=15)
