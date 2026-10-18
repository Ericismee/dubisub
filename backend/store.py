"""SQLite migrations and atomic, revision-checked project documents."""
import json
import os
import sqlite3
from pathlib import Path
from uuid import uuid4


class ClosingConnection(sqlite3.Connection):
    def __exit__(self, *args):
        try:
            return super().__exit__(*args)
        finally:
            self.close()


def root():
    path = Path(os.environ.get('DUBISUB_DATA_DIR', 'data')).resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def connect():
    db = sqlite3.connect(root() / 'dubisub.sqlite3', timeout=15, factory=ClosingConnection)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    db.execute('PRAGMA journal_mode=WAL')
    return db


def migrate():
    # Hold the schema lock across every version; API and worker can start together.
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        version=db.execute('PRAGMA user_version').fetchone()[0]
        if version>4:
            raise RuntimeError('Database schema is newer than this application')
        if version<1:
            db.execute('CREATE TABLE projects(id TEXT PRIMARY KEY, document TEXT NOT NULL)')
            db.execute('CREATE TABLE assets(id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id), filename TEXT NOT NULL, path TEXT NOT NULL, kind TEXT NOT NULL, checksum TEXT NOT NULL, metadata TEXT)')
            db.execute("CREATE TABLE jobs(id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id), asset_id TEXT NOT NULL REFERENCES assets(id), kind TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'queued', attempts INTEGER NOT NULL DEFAULT 0, progress INTEGER NOT NULL DEFAULT 0, heartbeat REAL, owner TEXT, error TEXT, checkpoint TEXT)")
        if version<2:
            db.execute('CREATE TABLE settings(id INTEGER PRIMARY KEY CHECK(id=1), providers TEXT NOT NULL)')
        if version<3:
            db.execute('CREATE TABLE link_imports(id TEXT PRIMARY KEY REFERENCES assets(id), url TEXT NOT NULL, inspection TEXT)')
            db.execute('CREATE TABLE asset_origins(asset_id TEXT PRIMARY KEY REFERENCES assets(id), source_url TEXT NOT NULL, imported_at REAL NOT NULL, language TEXT NOT NULL, automatic INTEGER NOT NULL)')
            db.execute("ALTER TABLE jobs ADD COLUMN payload TEXT NOT NULL DEFAULT '{}'")
        if version<4:
            db.execute('CREATE TABLE provider_checks(signature TEXT PRIMARY KEY, document TEXT NOT NULL)')
            db.execute('CREATE TABLE pipelines(id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id), document TEXT NOT NULL)')
        db.execute('PRAGMA user_version=4')


def project(db, project_id):
    row = db.execute('SELECT document FROM projects WHERE id=?', (project_id,)).fetchone()
    if row is None:
        raise KeyError(project_id)
    document=json.loads(row[0])
    if document.get('deleted'):
        raise KeyError(project_id)
    return document


def save(db, document):
    document['revision'] += 1
    db.execute('UPDATE projects SET document=? WHERE id=?',
               (json.dumps(document, ensure_ascii=False), document['id']))


def uid():
    return str(uuid4())
