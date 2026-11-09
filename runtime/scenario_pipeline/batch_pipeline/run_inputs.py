"""Immutable run-scoped law restrictions and indexed few-shot references."""
import json
from pathlib import Path
from .store import atomic, digest


def partition_snapshot(store):
    from law_split import active_manifest
    from recording_store import sha
    root=Path(store.path).resolve().parent.parent
    manifest=active_manifest(root)
    if not manifest:return {}
    pointer=json.loads((root/'sets/index.json').read_text())
    return {'version':manifest['version'],'manifest':pointer['law_split_manifest'],
            'manifest_sha256':sha(root/pointer['law_split_manifest']),
            'training_law_ids':manifest['training_law_ids'],'heldout_law_ids':manifest['heldout_law_ids']}


def freeze_inputs(store, catalog_id, laws, fewshots, output):
    partition=partition_snapshot(store)
    if not laws and not fewshots:
        return {'law_split':partition} if partition else {}
    source = json.loads(store.db.execute('SELECT payload FROM catalogs WHERE id=?', (catalog_id,)).fetchone()[0])
    frozen = {'law_split':partition} if partition else {}
    if laws:
        records = {}
        for line in Path(laws).read_text().splitlines():
            if not line.strip():
                continue
            law = json.loads(line)
            key = law['id']
            if key in records:
                raise ValueError('Duplicate scoped law: '+key)
            if key not in source['law_records'] or law['text'] != source['law_records'][key]['text']:
                raise ValueError('Scoped law does not match catalog: '+key)
            records[key] = law
        if not records:
            raise ValueError('Law restriction cannot be empty')
        frozen['law_scope'] = {'source': str(Path(laws).resolve()), 'records': records, 'version': digest(records)}
        definitions = Path(laws).parent/'definitions.jsonl'
        if definitions.exists():
            frozen['law_definitions'] = [json.loads(line) for line in definitions.read_text().splitlines() if line.strip()]
    if fewshots:
        root = Path(fewshots).resolve()
        examples = []
        for index in sorted(root.glob('*/example.json')):
            folder = index.parent
            files = {'example.json': index.read_text()}
            if (folder/'README.md').exists():
                files['README.md'] = (folder/'README.md').read_text()
            # One representative case per set is enough to teach construction;
            # the full index retains all comparisons and their limitations.
            first = json.loads(index.read_text()).get('cases', [])[:1]
            for case in first:
                case_root = folder/case.get('evidence_directory', str(Path(case.get('config', 'cases/'+case['case_id'])).parent))
                for name in ('runner.py', 'case.json', 'config.json', 'case_config_snapshot.json', 'result.json'):
                    path = case_root/name
                    if path.exists():
                        files[str(path.relative_to(folder))] = path.read_text()
            for field in ('relevance', 'bindings', 'cases'):
                path = folder/'inputs/motor_vehicle_driver'/(field+'.json')
                if path.exists():
                    value = json.loads(path.read_text())
                    if field == 'cases':
                        value['cases'] = value.get('cases', [])[:2]
                        value['sweep_specs'] = value.get('sweep_specs', [])[:1]
                    files[str(path.relative_to(folder))] = json.dumps(value)
            examples.append({'name': folder.name, 'source': str(folder), 'files': files, 'version': digest(files)})
        if not examples:
            raise ValueError('Fewshot directory has no indexed examples')
        frozen['fewshots'] = {'examples': examples, 'version': digest(examples),
            'policy': 'Draft historical references only. No inherited observations, tolerances, thresholds, laws or pilot geometry.'}
    frozen['judgment_completion_policy'] = {'scope': 'judgment_sweeps_only', 'interior_must_complete': True,
        'max_incomplete_per_endpoint': 1, 'endpoint_definition': 'frozen one-dimensional minimum/maximum',
        'on_violation': 'fail acceptance; preserve attempts; no endpoint redefinition or gap filling'}
    frozen['run_inputs_version'] = digest(frozen)
    path = Path(output)/'inputs/run_inputs.json'
    if path.exists():
        raise ValueError('Frozen run inputs already exist')
    atomic(path, frozen)
    return frozen


def stage_examples(snapshot, stage):
    examples = []
    for example in snapshot['examples']:
        files = {name: text for name, text in example['files'].items()
                 if (stage == 'cases' and (name in ('README.md','example.json') or name.endswith('/cases.json')))
                 or (stage == 'construction' and (name in ('README.md','example.json') or name.endswith(('runner.py','case.json','case_config_snapshot.json','result.json'))))}
        examples.append(dict(example, files=files))
    return {'policy': snapshot['policy'], 'version': snapshot['version'], 'examples': examples}


def freeze_job_revision(store, run, catalog_payload, config, provenance):
    """Freeze continuation inputs without changing the run's historical config.

    The exact content hash includes review metadata and source receipts. Callers
    select this revision explicitly on a root job; descendants inherit it.
    """
    import hashlib
    from .store import encode
    partition=partition_snapshot(store)
    if partition:config=dict(config,law_split=partition)
    value = {'catalog': catalog_payload, 'config': config, 'provenance': provenance}
    if not store.db.execute('SELECT 1 FROM runs WHERE id=?', (run,)).fetchone():
        raise ValueError('Unknown run for input revision: '+run)
    for law, record in config.get('law_scope', {}).get('records', {}).items():
        if catalog_payload.get('law_records', {}).get(law, {}).get('text') != record.get('text'):
            raise ValueError('Revision scope text differs from revision catalog: '+law)
    content = encode(value)
    revision = hashlib.sha256(content.encode()).hexdigest()
    store.db.execute('CREATE TABLE IF NOT EXISTS input_revisions ('
                     'run_id TEXT NOT NULL, id TEXT NOT NULL, payload TEXT NOT NULL, '
                     'PRIMARY KEY(run_id,id))')
    store.db.execute("CREATE TRIGGER IF NOT EXISTS immutable_input_revision_update "
                     "BEFORE UPDATE ON input_revisions BEGIN "
                     "SELECT RAISE(ABORT, 'Input revisions are immutable'); END")
    store.db.execute("CREATE TRIGGER IF NOT EXISTS immutable_input_revision_delete "
                     "BEFORE DELETE ON input_revisions BEGIN "
                     "SELECT RAISE(ABORT, 'Input revisions are immutable'); END")
    store.db.execute('INSERT OR IGNORE INTO input_revisions VALUES(?,?,?)',
                     (run, revision, content))
    return revision


def job_revision(store, run, revision):
    """Resolve only an explicitly requested immutable job revision."""
    import hashlib
    row = store.db.execute('SELECT payload FROM input_revisions WHERE run_id=? AND id=?',
                           (run, revision)).fetchone()
    if row is None or hashlib.sha256(row[0].encode()).hexdigest() != revision:
        raise ValueError('Missing or corrupt job input revision: '+revision)
    return json.loads(row[0])
