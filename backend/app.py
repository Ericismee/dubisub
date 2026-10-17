import hashlib
import json
import os
import shutil
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

import langcodes
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field, field_validator
from starlette.concurrency import run_in_threadpool
from . import store
from .subtitles import parse, validate, export


@asynccontextmanager
async def lifespan(app):
    store.migrate()
    yield


app = FastAPI(title='DubiSub', lifespan=lifespan)


@app.middleware('http')
async def local_requests(request, call_next):
    # Browser clients may mutate only from the local UI/API origins.
    origin = request.headers.get('origin')
    allowed = {'http://127.0.0.1:3600', 'http://localhost:3600', 'http://127.0.0.1:6060', 'http://localhost:6060'}
    if request.method not in ('GET', 'HEAD', 'OPTIONS') and origin and origin not in allowed:
        return Response('Untrusted browser origin', status_code=403)
    if request.url.path.endswith('/upload'):
        length = request.headers.get('content-length')
        if not length or not length.isdigit():
            return Response('Upload requires Content-Length', status_code=411)
        if int(length) > int(os.getenv('DUBISUB_MAX_UPLOAD_MB', '2048')) * 1024**2 + 1024**2:
            return Response('Upload request exceeds limit', status_code=413)
    return await call_next(request)


@app.exception_handler(KeyError)
async def missing(request, exc):
    return Response('Resource not found', status_code=404)


@app.exception_handler(ValueError)
async def invalid(request, exc):
    return Response(str(exc), status_code=422)


class CreateProject(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    mode: Literal['full', 'review'] = 'full'
    target_language: str = 'vi'

    @field_validator('target_language')
    @classmethod
    def language(cls, value):
        try:
            if not langcodes.tag_is_valid(value):
                raise ValueError('Invalid BCP 47 language')
            return langcodes.standardize_tag(value)
        except (ValueError, langcodes.LanguageTagError):
            raise ValueError('Invalid BCP 47 language')


class Cue(BaseModel):
    id: str = Field(min_length=1, max_length=100)
    start_ms: int = Field(strict=True)
    end_ms: int = Field(strict=True)
    text: str = Field(max_length=10000)


class EditTrack(BaseModel):
    revision: int
    cues: list[Cue] = Field(max_length=20000)


@app.get('/health')
def health():
    with store.connect() as db:
        db.execute('SELECT 1')
    return {'status': 'ok', 'product': 'DubiSub', 'schema_version': 2}


class ProviderConfig(BaseModel):
    kind: Literal['asr', 'translation', 'tts']
    endpoint: str = Field(max_length=2048)
    model: str = Field(default='', max_length=160)
    key_env: str = Field(default='', pattern=r'^(DUBISUB_[A-Z0-9_]{1,80})?$')

    @field_validator('endpoint')
    @classmethod
    def endpoint_url(cls, value):
        parts = urlsplit(value)
        if parts.scheme not in ('http', 'https') or not parts.hostname or parts.username or parts.password or parts.query or parts.fragment:
            raise ValueError('Endpoint must be HTTP(S) with no credentials, query or fragment')
        return value.rstrip('/')


class SettingsEdit(BaseModel):
    providers: list[ProviderConfig] = Field(max_length=3)


@app.put('/api/settings')
def update_settings(body: SettingsEdit):
    if len({p.kind for p in body.providers}) != len(body.providers):
        raise HTTPException(422, 'Only one configuration per provider kind')
    with store.connect() as db:
        db.execute('INSERT INTO settings VALUES(1,?) ON CONFLICT(id) DO UPDATE SET providers=excluded.providers',
                   (json.dumps([p.model_dump() for p in body.providers]),))
    return settings()


@app.get('/api/settings')
def settings():
    with store.connect() as db:
        row = db.execute('SELECT providers FROM settings WHERE id=1').fetchone()
    providers = json.loads(row[0]) if row else []
    providers = [dict(**p, verified=False, capabilities=[], key_present=bool(p['key_env'] and os.getenv(p['key_env']))) for p in providers]
    return {'max_upload_mb': int(os.getenv('DUBISUB_MAX_UPLOAD_MB', '2048')),
            'providers': providers, 'ai_status': 'unverified' if providers else 'not_configured',
            'ffmpeg_available': bool(shutil.which(os.getenv('DUBISUB_FFMPEG', 'ffmpeg'))),
            'ffprobe_available': bool(shutil.which(os.getenv('DUBISUB_FFPROBE', 'ffprobe')))}


@app.get('/api/projects')
def projects():
    with store.connect() as db:
        return [json.loads(r[0]) for r in db.execute('SELECT document FROM projects ORDER BY rowid DESC')]


@app.post('/api/projects', status_code=201)
def create(body: CreateProject):
    document = dict(id=store.uid(), schema_version=1, revision=0, tracks=[], **body.model_dump())
    with store.connect() as db:
        db.execute('INSERT INTO projects VALUES (?,?)', (document['id'], json.dumps(document)))
    return document


@app.get('/api/projects/{project_id}')
def read(project_id: str):
    with store.connect() as db:
        document = store.project(db, project_id)
        document['assets'] = [dict(r) for r in db.execute(
            'SELECT id,filename,kind,checksum,metadata FROM assets WHERE project_id=?', (project_id,))]
        document['jobs'] = [dict(r) for r in db.execute(
            'SELECT id,kind,state,attempts,progress,error FROM jobs WHERE project_id=?', (project_id,))]
    return document


@app.post('/api/projects/{project_id}/upload', status_code=202)
async def upload(project_id: str, file: UploadFile = File(), kind: Literal['media', 'subtitle'] = Form()):
    with store.connect() as db:
        store.project(db, project_id)
    extension = Path(file.filename or '').suffix.lower().lstrip('.')
    if kind == 'subtitle' and extension not in ('srt', 'vtt', 'ass'):
        raise HTTPException(422, 'Choose SRT, VTT or ASS')
    asset_id = store.uid()
    directory = store.root() / 'assets'
    directory.mkdir(exist_ok=True)
    path = directory / asset_id  # Never use an untrusted filename as a filesystem path.
    cap = min(8 * 1024 * 1024, int(os.getenv('DUBISUB_MAX_UPLOAD_MB', '2048')) * 1024**2) if kind == 'subtitle' else int(os.getenv('DUBISUB_MAX_UPLOAD_MB', '2048')) * 1024**2
    size = 0
    digest = hashlib.sha256()
    try:
        with path.open('xb') as output:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > cap or shutil.disk_usage(directory).free < len(chunk) + 64 * 1024**2:
                    raise HTTPException(413, 'Upload limit or free disk reserve exceeded')
                digest.update(chunk)
                await run_in_threadpool(output.write, chunk)
        if not size:
            raise HTTPException(422, 'Empty file')
        cues = await run_in_threadpool(parse, path.read_text(encoding='utf-8-sig'), extension) if kind == 'subtitle' else None
        with store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            doc = store.project(db, project_id)
            db.execute('INSERT INTO assets VALUES (?,?,?,?,?,?,NULL)',
                       (asset_id, project_id, (file.filename or 'upload')[:255], str(path), kind, digest.hexdigest()))
            if cues is not None:
                doc['tracks'].append(dict(id=store.uid(), asset_id=asset_id, language='und', cues=cues))
                store.save(db, doc)
            else:
                db.execute('INSERT INTO jobs(id,project_id,asset_id,kind) VALUES (?,?,?,?)',
                           (store.uid(), project_id, asset_id, 'probe'))
        return {'asset_id': asset_id}
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    finally:
        await file.close()


@app.put('/api/projects/{project_id}/tracks/{track_id}')
def edit(project_id: str, track_id: str, body: EditTrack):
    cues = [c.model_dump() for c in body.cues]
    validate(cues)
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        doc = store.project(db, project_id)
        if doc['revision'] != body.revision:
            raise HTTPException(409, 'Project changed elsewhere; reopen before saving')
        track = next((t for t in doc['tracks'] if t['id'] == track_id), None)
        if track is None:
            raise KeyError(track_id)
        track['cues'] = cues
        store.save(db, doc)
    return doc


@app.get('/api/projects/{project_id}/tracks/{track_id}/export')
def download(project_id: str, track_id: str, format: Literal['srt', 'vtt'] = 'srt'):
    with store.connect() as db:
        doc = store.project(db, project_id)
    track = next((t for t in doc['tracks'] if t['id'] == track_id), None)
    if track is None:
        raise KeyError(track_id)
    return Response(export(track['cues'], format), media_type='text/vtt; charset=utf-8' if format == 'vtt' else 'text/plain; charset=utf-8',
                    headers={'Content-Disposition': f'attachment; filename="subtitles.{format}"'})


@app.get('/api/projects/{project_id}/assets/{asset_id}/content')
def media(project_id: str, asset_id: str):
    with store.connect() as db:
        row = db.execute('SELECT * FROM assets WHERE id=? AND project_id=? AND kind="media"',
                         (asset_id, project_id)).fetchone()
    if row is None:
        raise KeyError(asset_id)
    metadata = json.loads(row['metadata']) if row['metadata'] else {}
    fmt = metadata.get('format', {}).get('format_name', '')
    mime = 'video/webm' if 'webm' in fmt else ('video/mp4' if 'mov' in fmt else 'application/octet-stream')
    return FileResponse(row['path'], media_type=mime, filename=row['filename'], content_disposition_type='inline')


@app.post('/api/jobs/{job_id}/{action}')
def control(job_id: str, action: Literal['cancel', 'retry']):
    with store.connect() as db:
        if action == 'cancel':
            result = db.execute("UPDATE jobs SET state='canceled' WHERE id=? AND state IN ('queued','running')", (job_id,))
        else:
            result = db.execute("UPDATE jobs SET state='queued',error=NULL,progress=0 WHERE id=? AND state IN ('failed','canceled') AND attempts<3", (job_id,))
        if not result.rowcount:
            raise HTTPException(409, 'Job missing, not eligible, or retry limit reached')
    return {'status': action}
