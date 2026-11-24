"""Transactional jobs, immutable artifacts, and the shared law library."""
import hashlib
import json
import sqlite3
import time
import tempfile
from contextlib import contextmanager
from pathlib import Path

REVIEW_KEYS = {'review_status', 'reviewed_at', 'approval', 'provenance', 'dependency_reviews'}


def semantic(value):
    if isinstance(value, dict):
        return {k: semantic(v) for k, v in value.items() if k not in REVIEW_KEYS
                and not (k == 'status' and v in ('draft', 'approved', 'reviewed', 'unreviewed', 'awaiting_review'))}
    if isinstance(value, list):
        return [semantic(v) for v in value]
    return value


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def digest(value):
    return hashlib.sha256(encode(semantic(value)).encode()).hexdigest()


def atomic(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(value, indent=2, ensure_ascii=False) + '\n'
    if path.exists() and path.read_text() == content:
        return
    # Unique temporary files support simultaneous status/export processes.
    with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, prefix=path.name+'.', delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(content)
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


class Store:
    def __init__(self, path):
        self.path = Path(path).resolve()
        if self.path.exists():
            with sqlite3.connect(self.path.as_uri()+'?mode=ro', uri=True) as probe:
                if probe.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='runs'").fetchone():
                    if any(json.loads(row[0]).get('judgment_policy') != 'fixed_sweeps' for row in probe.execute('SELECT config FROM runs')):
                        raise ValueError('Old pipeline state is unsupported; use a fresh database. Historical state was not modified.')
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(self.path), timeout=30, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA foreign_keys=ON')
        self.db.execute('PRAGMA busy_timeout=30000')
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS catalogs(id TEXT PRIMARY KEY, source TEXT, payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS cells(catalog_id TEXT, cell_id TEXT, layout TEXT, maneuver TEXT,
            control TEXT, grounding TEXT, actor_status TEXT, payload TEXT,
            PRIMARY KEY(catalog_id,cell_id));
        CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY, catalog_id TEXT, output TEXT, config TEXT, created REAL);
        CREATE TABLE IF NOT EXISTS jobs(id INTEGER PRIMARY KEY, cache_key TEXT UNIQUE, stage TEXT,
            entity TEXT, actor TEXT, payload TEXT, status TEXT DEFAULT 'pending', attempts INTEGER DEFAULT 0,
            available REAL DEFAULT 0, lease_until REAL, owner TEXT, error TEXT, artifact_id TEXT);
        CREATE INDEX IF NOT EXISTS ready_jobs ON jobs(status,available,stage);
        CREATE TABLE IF NOT EXISTS run_jobs(run_id TEXT, job_id INTEGER, active INTEGER NOT NULL DEFAULT 1, PRIMARY KEY(run_id,job_id));
        CREATE TABLE IF NOT EXISTS dependencies(job_id INTEGER, dependency_id INTEGER,
            PRIMARY KEY(job_id,dependency_id));
        CREATE INDEX IF NOT EXISTS parent_children ON dependencies(dependency_id,job_id);
        CREATE INDEX IF NOT EXISTS job_entities ON jobs(stage,entity,actor);
        CREATE TABLE IF NOT EXISTS artifacts(id TEXT PRIMARY KEY, job_id INTEGER, payload TEXT,
            provenance TEXT, review_status TEXT, reviewed_at TEXT, created REAL);
        CREATE TABLE IF NOT EXISTS templates(template_id TEXT PRIMARY KEY, payload TEXT, version TEXT);
        CREATE TABLE IF NOT EXISTS template_history(template_id TEXT,version TEXT,payload TEXT,
            PRIMARY KEY(template_id,version));
        CREATE TABLE IF NOT EXISTS attempts(id INTEGER PRIMARY KEY,job_id INTEGER,number INTEGER,
            started REAL,ended REAL,error TEXT,metadata TEXT);
        CREATE TABLE IF NOT EXISTS resource_leases(resource TEXT PRIMARY KEY,owner TEXT,expires REAL);
        CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY,job_id INTEGER,created REAL,message TEXT);
        ''')

    @contextmanager
    def transaction(self):
        self.db.execute('BEGIN IMMEDIATE')
        try:
            yield
            self.db.execute('COMMIT')
        except BaseException:
            self.db.execute('ROLLBACK')
            raise

    def close(self):
        self.db.close()

    def job(self, ident):
        r = self.db.execute('SELECT * FROM jobs WHERE id=?', (ident,)).fetchone()
        return dict(r) if r else None

    def artifact(self, ident):
        row = self.db.execute('SELECT * FROM artifacts WHERE id=?', (ident,)).fetchone()
        if not row:
            raise ValueError('Missing artifact ' + str(ident))
        r = dict(row)
        r['payload'] = json.loads(r['payload'])
        r['provenance'] = json.loads(r['provenance'])
        return r

    def enqueue(self, run, stage, entity, actor, payload, skill_hash, dependencies=()):
        # Stable logical dependency keys allow identical work to be reused across runs.
        deps = [self.job(d)['cache_key'] for d in dependencies]
        key = digest([stage, entity, actor, payload, skill_hash, sorted(deps)])
        self.db.execute('INSERT OR IGNORE INTO jobs(cache_key,stage,entity,actor,payload) VALUES(?,?,?,?,?)',
                        (key, stage, entity, actor, encode(payload)))
        ident = self.db.execute('SELECT id FROM jobs WHERE cache_key=?', (key,)).fetchone()[0]
        self.db.execute('UPDATE run_jobs SET active=0 WHERE run_id=? AND job_id IN (SELECT id FROM jobs WHERE stage=? AND entity=? AND actor=? AND id!=?)',
                        (run, stage, entity, actor, ident))
        self.db.execute('INSERT INTO run_jobs(run_id,job_id,active) VALUES(?,?,1) ON CONFLICT(run_id,job_id) DO UPDATE SET active=1', (run, ident))
        for dep in dependencies:
            self.db.execute('INSERT OR IGNORE INTO dependencies VALUES(?,?)', (ident, dep))
        return ident

    def claim(self, run, owner, stages, lease=180, job_ids=()):
        now = time.time()
        job_filter = 'AND j.id IN ('+','.join('?' for _ in job_ids)+')' if job_ids else ''
        with self.transaction():
            self.db.execute("UPDATE attempts SET ended=?,error='Lease expired; recovered after interruption' WHERE ended IS NULL AND job_id IN (SELECT id FROM jobs WHERE status='running' AND lease_until<?)", (now, now))
            self.db.execute("UPDATE jobs SET status='pending',owner=NULL,lease_until=NULL WHERE status='running' AND stage!='execution' AND lease_until<?", (now,))
            self.db.execute("UPDATE jobs SET status='failed',owner=NULL,lease_until=NULL,error='Interrupted execution retained; no automatic rerun' WHERE status='running' AND stage='execution' AND lease_until<?", (now,))
            row = self.db.execute('''SELECT j.* FROM jobs j JOIN run_jobs r ON r.job_id=j.id
                WHERE r.run_id=? AND r.active=1 AND j.status='pending' AND j.available<=?
                AND j.stage IN (%s) AND NOT EXISTS (
                    SELECT 1 FROM dependencies d JOIN jobs parent ON parent.id=d.dependency_id
                    WHERE d.job_id=j.id AND parent.status!='completed')
                %s ORDER BY j.id LIMIT 1''' % (','.join('?' for _ in stages), job_filter), (run, now, *stages, *job_ids)).fetchone()
            if not row:
                return None
            self.db.execute("UPDATE jobs SET status='running',owner=?,lease_until=?,attempts=attempts+1,error=NULL WHERE id=?", (owner, now+lease, row['id']))
            self.db.execute('INSERT INTO attempts(job_id,number,started) VALUES(?,?,?)', (row['id'], row['attempts']+1, now))
            claimed = self.job(row['id'])
            claimed['error'] = row['error']
            return claimed

    def heartbeat(self, ident, owner, lease=180):
        cur = self.db.execute("UPDATE jobs SET lease_until=? WHERE id=? AND owner=? AND status='running'", (time.time()+lease, ident, owner))
        return cur.rowcount == 1

    def finish(self, job, owner, payload, provenance, metadata, expand=None):
        with self.transaction():
            current = self.job(job['id'])
            if current['owner'] != owner or current['status'] != 'running':
                raise RuntimeError('Lost job lease')
            revision = json.loads(current['payload']).get('input_revision')
            if revision:
                if provenance.get('input_revision', revision) != revision:
                    raise ValueError('Artifact input revision differs from its job')
                provenance = dict(provenance, input_revision=revision)
            ident = digest([job['cache_key'], payload])
            self.db.execute('INSERT OR IGNORE INTO artifacts VALUES(?,?,?,?,?,?,?)',
                (ident, job['id'], encode(payload), encode(provenance), 'unreviewed', None, time.time(),))
            # Shared library writes and dependent-job creation are atomic with completion.
            if expand:
                expand(ident)
            self.db.execute("UPDATE jobs SET status='completed',artifact_id=?,owner=NULL,lease_until=NULL WHERE id=?", (ident, job['id']))
            self.db.execute('UPDATE attempts SET ended=?,metadata=? WHERE job_id=? AND number=?',
                (time.time(), encode(metadata), job['id'], current['attempts']))
            return ident

    def fail(self, job, owner, error, retry=False, delay=0, blocked=False, metadata=None):
        status = 'pending' if retry else ('blocked' if blocked else 'failed')
        with self.transaction():
            cur = self.db.execute('UPDATE jobs SET status=?,error=?,available=?,owner=NULL,lease_until=NULL WHERE id=? AND owner=?',
                (status, str(error), time.time()+delay, job['id'], owner))
            if cur.rowcount:
                self.db.execute('UPDATE attempts SET ended=?,error=?,metadata=? WHERE job_id=? AND number=?',
                    (time.time(), str(error), encode(metadata or {}), job['id'], job['attempts']))
                self.db.execute('INSERT INTO events(job_id,created,message) VALUES(?,?,?)', (job['id'], time.time(), str(error)))

    def merge_template(self, value):
        from .validation import no_interpretations
        no_interpretations(value)
        key = value['template_id']
        identities = [(j['phrase'], j.get('note', '')) for j in value['structure']['judgment_calls_needed']]
        if len(identities) != len(set(identities)):
            raise ValueError('Ambiguous duplicate judgment entry: '+key)
        old = self.db.execute('SELECT payload,version FROM templates WHERE template_id=?', (key,)).fetchone()
        if old:
            previous = json.loads(old['payload'])
            by_phrase = {(j['phrase'], j.get('note', '')): j for j in value['structure']['judgment_calls_needed']}
            for j in previous['structure']['judgment_calls_needed']:
                if j.get('observable_requirements'):
                    match = by_phrase.get((j['phrase'], j.get('note', '')))
                    if match is None:
                        raise ValueError('Template regeneration would erase observable requirements: '+key)
                    for field in ('observable_requirements',):
                        if field in j:
                            if field in match and match[field] != j[field]:
                                raise ValueError('Conflicting observable replacement: '+key)
                            match[field] = j[field]
            self.db.execute('INSERT OR IGNORE INTO template_history VALUES(?,?,?)', (key, old['version'], old['payload']))
        version = digest(value)
        self.db.execute('INSERT OR REPLACE INTO templates VALUES(?,?,?)', (key, encode(value), version))
        return version

    def adopt_observable_extension(self, artifact_id, expected_version):
        """Adopt a validated append-only physical-measurement revision.

        Existing reviewed entries and template history remain immutable. The
        caller supplies an already completed judgment_observables artifact and
        the exact current template version; ordinary merge remains strict.
        """
        import copy
        from .validation import observable_requirements, no_interpretations
        artifact = self.artifact(artifact_id)
        completed = self.db.execute(
            "SELECT 1 FROM jobs WHERE artifact_id=? AND stage='judgment_observables' AND status='completed'",
            (artifact_id,)).fetchone()
        if not completed:
            raise ValueError('Extension requires a completed observable artifact')
        result = artifact['payload']
        key = result['template_id']
        current = self.get_template(key)
        if current is None or digest(current) != expected_version:
            raise ValueError('Observable extension base version changed')
        updated = copy.deepcopy(current)
        matches = [j for j in updated['structure']['judgment_calls_needed']
                   if (j['phrase'], j.get('note', '')) == (result['phrase'], result.get('note', ''))]
        if len(matches) != 1:
            raise ValueError('Ambiguous observable extension identity')
        previous = matches[0].get('observable_requirements')
        proposed = result['observable_requirements']
        observable_requirements(proposed)
        if not previous or set(previous) != set(proposed):
            raise ValueError('Extension cannot replace the requirement schema')
        additions = 0
        for field, entries in previous.items():
            target = proposed[field]
            if not isinstance(entries, list) or not isinstance(target, list):
                raise ValueError('Only list extensions are supported')
            if any(entry not in target for entry in entries):
                raise ValueError('Extension would change or erase existing evidence requirements')
            additions += len(target) - len(entries)
            if field != 'limitations':
                names = [entry['name'] for entry in target]
                if len(names) != len(set(names)):
                    raise ValueError('Extension cannot redefine an existing measurement name')
        if additions <= 0:
            raise ValueError('No added measurement requirements')
        matches[0]['observable_requirements'] = copy.deepcopy(proposed)
        no_interpretations(updated)
        version = digest(updated)
        with self.transaction():
            row = self.db.execute('SELECT version FROM templates WHERE template_id=?', (key,)).fetchone()
            if row is None or row[0] != expected_version:
                raise ValueError('Observable extension base changed during adoption')
            self.db.execute('INSERT OR IGNORE INTO template_history VALUES(?,?,?)',
                            (key, expected_version, encode(current)))
            self.db.execute('INSERT OR REPLACE INTO templates VALUES(?,?,?)',
                            (key, encode(updated), version))
        return version

    def get_template(self, key, version=None):
        row = self.db.execute('SELECT payload,version FROM templates WHERE template_id=?', (key,)).fetchone()
        if version is not None and row and row['version'] != version:
            row = self.db.execute('SELECT payload FROM template_history WHERE template_id=? AND version=?', (key, version)).fetchone()
        return json.loads(row[0]) if row else None
