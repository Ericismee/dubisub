"""One bounded media process at a time; durable claim, lease and idempotent commit."""
import json
import os
import subprocess
import tempfile
import time
import shutil
import sys
from pathlib import Path
from . import store
from .subtitles import parse

OWNER = store.uid()
FORMATS = 'mov,matroska,webm,avi,mp3,wav,flac,ogg,mpegts,mpeg,aac'


class Canceled(Exception):
    pass


def command(args, job, timeout=120):
    with tempfile.TemporaryFile() as output, tempfile.TemporaryFile() as errors:
        process = subprocess.Popen(args, stdout=output, stderr=errors, stdin=subprocess.DEVNULL)
        started = time.monotonic()
        try:
            while process.poll() is None:
                with store.connect() as db:
                    updated = db.execute("UPDATE jobs SET heartbeat=? WHERE id=? AND owner=? AND state='running'",
                                         (time.time(), job['id'], OWNER)).rowcount
                if not updated:
                    raise Canceled()
                if time.monotonic() - started > timeout:
                    raise ValueError('Tác vụ media đã hết thời gian cho phép.')
                if output.tell() > 8 * 1024**2 or errors.tell() > 2 * 1024**2:
                    raise ValueError('Media inspection output exceeds limit')
                time.sleep(.15)
            if process.returncode:
                # Avoid returning paths, URL tokens or metadata-controlled stderr.
                raise ValueError('FFmpeg/FFprobe could not read this media or subtitle track')
            output.seek(0)
            data = output.read(8 * 1024**2 + 1)
            if len(data) > 8 * 1024**2:
                raise ValueError('Media output exceeds 8 MiB limit')
            return data.decode('utf-8')
        finally:
            if process.poll() is None:
                process.kill()
            process.wait()


def finish_link(job, result):
    if 'error' in result:
        raise ValueError(result['error'])
    if result.get('inspected'):
        with store.connect() as db:
            db.execute("UPDATE jobs SET state='succeeded',progress=100,checkpoint='metadata-inspected',error=NULL WHERE id=? AND owner=? AND state='running'", (job['id'],OWNER))
        return
    files=result['files']
    staging=(store.root()/'staging'/job['id']).resolve()
    if any(not Path(item['path']).resolve().is_relative_to(staging) for item in files):
        raise ValueError('Đường dẫn staging không hợp lệ.')
    audio=next((item for item in files if item['kind']=='audio_merge'),None)
    media=next((item for item in files if item['kind']=='media'),None)
    if audio and media:
        merged=staging/'merged.mp4'
        command([os.getenv('DUBISUB_FFMPEG','ffmpeg'),'-v','error','-nostdin','-protocol_whitelist','file,pipe','-format_whitelist',FORMATS,
                 '-i',media['path'],'-protocol_whitelist','file,pipe','-format_whitelist',FORMATS,'-i',audio['path'],
                 '-map','0:v:0','-map','1:a:0','-c','copy','-movflags','+faststart','-y',str(merged)],job,timeout=600)
        media['path'],media['ext']=str(merged),'mp4'
    tracks=[]; prepared=[]; moved=[]
    directory=store.root()/'assets';directory.mkdir(exist_ok=True)
    for item in files:
        if item['kind']=='audio_merge':continue
        path=Path(item['path'])
        if path.stat().st_size>int(os.getenv('DUBISUB_MAX_UPLOAD_MB','2048'))*1024**2:
            raise ValueError('Media nhập vượt giới hạn dung lượng.')
        aid=store.uid(); destination=directory/aid
        if item['kind']=='subtitle':
            cues=parse(path.read_text(encoding='utf-8-sig'),item['ext'])
            tracks.append(dict(id=store.uid(),asset_id=aid,language=item['language'],automatic=item['automatic'],cues=cues))
        digest=__import__('hashlib').sha256()
        with path.open('rb') as source:
            while chunk:=source.read(1024**2):digest.update(chunk)
        base=result['title'][:180]
        title=(base if base.lower().endswith('.'+item['ext']) else base+'.'+item['ext']).replace('\x00','')
        prepared.append((aid,item,path,destination,digest.hexdigest(),title))
    try:
        with store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if not db.execute("SELECT id FROM jobs WHERE id=? AND owner=? AND state='running'",(job['id'],OWNER)).fetchone():
                raise Canceled()
            doc=store.project(db,job['project_id'])
            for aid,item,path,destination,checksum,title in prepared:
                path.replace(destination);moved.append(destination)
                db.execute('INSERT INTO assets VALUES(?,?,?,?,?,?,NULL)',(aid,job['project_id'],title,str(destination),item['kind'],checksum))
                db.execute('INSERT INTO asset_origins VALUES(?,?,?,?,?)',(aid,result['source_url'],time.time(),item['language'],int(item['automatic'])))
                if item['kind']=='media':
                    db.execute("INSERT INTO jobs(id,project_id,asset_id,kind) VALUES(?,?,?,'probe')",(store.uid(),job['project_id'],aid))
            doc['tracks'].extend(tracks);store.save(db,doc)
            db.execute("UPDATE jobs SET state='succeeded',progress=100,checkpoint='import-committed',error=NULL WHERE id=?",(job['id'],))
    except BaseException:
        for path in moved:path.unlink(missing_ok=True)
        raise


def run_once(*, link_executor=None):
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        db.execute("UPDATE jobs SET state=CASE WHEN attempts<3 THEN 'queued' ELSE 'failed' END,error='Recovered interrupted worker' WHERE state='running' AND heartbeat<?", (time.time()-30,))
        row = db.execute("SELECT jobs.*,assets.path FROM jobs JOIN assets ON assets.id=jobs.asset_id WHERE state='queued' ORDER BY jobs.rowid LIMIT 1").fetchone()
        if row is None:
            return False
        job = dict(row)
        db.execute("UPDATE jobs SET state='running',attempts=attempts+1,heartbeat=?,owner=?,progress=10 WHERE id=?", (time.time(), OWNER, job['id']))
    try:
        if job['kind'] in ('inspect_link','download_link'):
            result=link_executor(job['id']) if link_executor else json.loads(command([sys.executable,'-m','backend.link_tasks',job['id']],job,timeout=180 if job['kind']=='inspect_link' else 10800))
            finish_link(job,result)
            return True
        metadata = json.loads(command([os.getenv('DUBISUB_FFPROBE', 'ffprobe'), '-v', 'error', '-protocol_whitelist', 'file,pipe', '-format_whitelist', FORMATS,
                                      '-show_format', '-show_streams', '-of', 'json', job['path']], job))
        streams = metadata.get('streams', [])
        if not any(s['codec_type'] in ('video', 'audio') for s in streams):
            raise ValueError('No audio or video stream detected')
        tracks = []
        for stream in streams:
            if stream.get('codec_type') == 'subtitle' and stream.get('codec_name') in ('subrip', 'ass', 'ssa', 'webvtt', 'mov_text'):
                text = command([os.getenv('DUBISUB_FFMPEG', 'ffmpeg'), '-v', 'error', '-nostdin', '-protocol_whitelist', 'file,pipe', '-format_whitelist', FORMATS,
                                '-i', job['path'], '-map', f'0:{stream["index"]}', '-f', 'srt', 'pipe:1'], job)
                if text.strip():
                    tracks.append(dict(id=store.uid(), asset_id=job['asset_id'], stream_index=stream['index'],
                                       language=stream.get('tags', {}).get('language', 'und'), cues=parse(text, 'srt')))
        # No checkpoint is committed separately from project data: retries cannot duplicate tracks.
        with store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            active = db.execute("SELECT id FROM jobs WHERE id=? AND owner=? AND state='running'", (job['id'], OWNER)).fetchone()
            if active:
                doc = store.project(db, job['project_id'])
                doc['tracks'].extend(tracks)
                store.save(db, doc)
                db.execute('UPDATE assets SET metadata=? WHERE id=?', (json.dumps(metadata), job['asset_id']))
                db.execute("UPDATE jobs SET state='succeeded',progress=100,checkpoint='probe-and-extract-committed',error=NULL WHERE id=?", (job['id'],))
    except Canceled:
        pass
    except Exception as exc:
        message = str(exc) if isinstance(exc, ValueError) else 'Media tool unavailable or worker failed; check FFmpeg installation'
        with store.connect() as db:
            db.execute("UPDATE jobs SET state='failed',error=? WHERE id=? AND owner=? AND state='running'", (message[:250], job['id'], OWNER))
    finally:
        if job['kind']=='download_link':
            staging=(store.root()/'staging'/job['id']).resolve()
            if staging.is_relative_to((store.root()/'staging').resolve()) and staging.exists():
                shutil.rmtree(staging)
    return True


def main():
    store.migrate()
    while True:
        if not run_once():
            time.sleep(.5)


if __name__ == '__main__':
    main()
