"""SQLite migrations and atomic, revision-checked project documents."""
import json
import os
import sqlite3
from pathlib import Path
from uuid import uuid4


def root():
    path = Path(os.environ.get('DUBISUB_DATA_DIR', 'data')).resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def connect():
    db = sqlite3.connect(root() / 'dubisub.sqlite3', timeout=15)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    db.execute('PRAGMA journal_mode=WAL')
    return db


def migrate():
    with connect() as db:
        version = db.execute('PRAGMA user_version').fetchone()[0]
        if version > 3:
            raise RuntimeError('Database schema is newer than this application')
        if version == 0:
            db.executescript('''
            BEGIN IMMEDIATE;
            CREATE TABLE IF NOT EXISTS projects(id TEXT PRIMARY KEY, document TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS assets(id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
                filename TEXT NOT NULL, path TEXT NOT NULL, kind TEXT NOT NULL, checksum TEXT NOT NULL,
                metadata TEXT);
            CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
                asset_id TEXT NOT NULL REFERENCES assets(id), kind TEXT NOT NULL,
                state TEXT NOT NULL DEFAULT 'queued', attempts INTEGER NOT NULL DEFAULT 0,
                progress INTEGER NOT NULL DEFAULT 0, heartbeat REAL, owner TEXT,
                error TEXT, checkpoint TEXT);
            PRAGMA user_version=1;
            COMMIT;
            ''')
        if version < 2:
            db.executescript('''
            BEGIN IMMEDIATE;
            CREATE TABLE IF NOT EXISTS settings(id INTEGER PRIMARY KEY CHECK(id=1), providers TEXT NOT NULL);
            PRAGMA user_version=2;
            COMMIT;
            ''')
        if version < 3:
            db.execute('BEGIN IMMEDIATE')
            if db.execute('PRAGMA user_version').fetchone()[0] < 3:
                db.execute('CREATE TABLE link_imports(id TEXT PRIMARY KEY REFERENCES assets(id), url TEXT NOT NULL, inspection TEXT)')
                db.execute('CREATE TABLE asset_origins(asset_id TEXT PRIMARY KEY REFERENCES assets(id), source_url TEXT NOT NULL, imported_at REAL NOT NULL, language TEXT NOT NULL, automatic INTEGER NOT NULL)')
                db.execute("ALTER TABLE jobs ADD COLUMN payload TEXT NOT NULL DEFAULT '{}'")
                db.execute('PRAGMA user_version=3')


def project(db, project_id):
    row = db.execute('SELECT document FROM projects WHERE id=?', (project_id,)).fetchone()
    if row is None:
        raise KeyError(project_id)
    return json.loads(row[0])


def save(db, document):
    document['revision'] += 1
    db.execute('UPDATE projects SET document=? WHERE id=?',
               (json.dumps(document, ensure_ascii=False), document['id']))


def uid():
    return str(uuid4())
