"""Build source-bound left-signal paragraph (a) pair as CPU drafts."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASE = HERE.parent
ROOT = CASE.parents[1]
BASE = HERE / 'selected-paragraph-d' / 'witness_1' / 'primary' / 'construction.json'
OUT = HERE / 'exception-1'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def build():
    plan = json.loads((CASE / 'case-plan.json').read_text())
    template = json.loads(BASE.read_text())
    original = CASE.name + '__witness_1'
    entries = []
    for index in (1, 2):
        suffix = 'exception_1_' + str(index)
        case_id = CASE.name + '__' + suffix
        requested = index == 2
        construction = json.loads(json.dumps(template))
        construction['case_id'] = case_id
        construction['status'] = 'exception_1_cpu_draft_physical_unverified'
        construction['measurement_plan'] = {
            'source': 'retained original Native lead light-state and actor/map/camera records',
            'finalizer': 'finalize.py', 'legal_verdict': None}
        files = {item['path']: item for item in construction['files']}
        config = json.loads(files['config.json']['content'])
        config.update(case_id=case_id, selected_case_id=case_id,
                      supported_case_ids=[CASE.name + '__exception_1_1',
                                          CASE.name + '__exception_1_2'],
                      case={'case_id': case_id},
                      lead_left_signal_requested=requested)
        rows = [json.loads(line) for line in files['requested-tracks.jsonl']['content'].splitlines()]
        for row in rows:
            row['case_id'] = case_id
            row['requested_lead_left_signal'] = requested
        tracks = ''.join(json.dumps(row, allow_nan=False) + '\n' for row in rows)
        files['requested-tracks.jsonl']['content'] = tracks
        config['tracks_sha256'] = hashlib.sha256(tracks.encode()).hexdigest()
        files['config.json']['content'] = json.dumps(config, indent=2, allow_nan=False) + '\n'
        check = files['check.py']['content'].replace('__witness_1', '__' + suffix)
        check = check.replace("    return {'case_id': cfg['case_id']", "    if cfg.get('lead_left_signal_requested') is not " + str(requested) + ":\n        raise ValueError('Left signal request differs')\n    return {'case_id': cfg['case_id']")
        files['check.py']['content'] = check
        files['saved.py']['content'] = files['saved.py']['content'].replace("endswith('__witness_1')", "endswith('__" + suffix + "')")
        finalize = files['finalize.py']['content']
        finalize = finalize.replace("('__witness_1', '__witness_2')", "('__exception_1_1', '__exception_1_2')")
        finalize = finalize.replace('values = measure_paragraph_d(metric)',
            "raw_signal = [json.loads(line) for line in (attempt / 'native-raw-actors.jsonl').read_text().splitlines()]\n"
            "    if any(type(row.get('observed_lead_left_blinker')) is not bool or row.get('requested_lead_left_signal') is not config['lead_left_signal_requested'] for row in raw_signal):\n"
            "        raise ValueError('Original lead signal state missing or request differs')\n"
            "    values = {'frames_joined': metric['frames_joined'], 'lead_left_blinker_frames': sum(row['observed_lead_left_blinker'] for row in raw_signal),\n"
            "              'requested_lead_left_signal': config['lead_left_signal_requested'], 'original_native_observed': metric['original_native_observed'],\n"
            "              'legal_signal_permission_reviewed': False}")
        finalize = finalize.replace('def finalize(attempt, output):',
            "def measure_left_signal(raw_signal, metric, requested):\n"
            "    return {'frames_joined': metric['frames_joined'], 'lead_left_blinker_frames': sum(row['observed_lead_left_blinker'] for row in raw_signal),\n"
            "            'requested_lead_left_signal': requested, 'original_native_observed': metric['original_native_observed'],\n"
            "            'legal_signal_permission_reviewed': False}\n\n\n"
            'def finalize(attempt, output):')
        finalize = finalize.replace("values = {'frames_joined': metric['frames_joined'], 'lead_left_blinker_frames': sum(row['observed_lead_left_blinker'] for row in raw_signal),\n              'requested_lead_left_signal': config['lead_left_signal_requested'], 'original_native_observed': metric['original_native_observed'],\n              'legal_signal_permission_reviewed': False}",
            "values = measure_left_signal(raw_signal, metric, config['lead_left_signal_requested'])")
        files['finalize.py']['content'] = finalize
        contract = json.loads(files['measurement-contract.json']['content'])
        contract['case_id'] = case_id
        contract['requirements'][0]['disposition_index'] = 1
        contract['requirements'][0]['method'] = 'measure_left_signal'
        contract['requirements'][0]['output_key'] = 'paragraph_a_left_signal_source_observation'
        files['measurement-contract.json']['content'] = json.dumps(contract, indent=2, allow_nan=False) + '\n'
        construction['recording_description']['limitations'].append(
            'The overtaken actor light-state request and observation do not establish legal permission or a left turn.')
        directory = OUT / suffix
        path = directory / 'primary' / 'construction.json'
        put(path, construction)
        put(directory / 'measurement-contract.json', contract)
        entries.append({'case_id': case_id, 'kind': 'delivery',
            'construction': suffix + '/primary/construction.json',
            'construction_sha256': sha(path),
            'measurement_contract': suffix + '/measurement-contract.json',
            'measurement_procedure': {'entrypoint': 'finalize.py'},
            'candidate_risk': {'status': 'physical',
                'reason': 'Original lead signal, right pass, and four source camera pixels remain unverified.'},
            'candidates': [],
            'native_handoff': {'python_env_var': 'CARLA_PYTHON',
                'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'}})
    runtime = json.loads((ROOT / 'batch.json').read_text())['runtime']['root']
    manifest = {'format': 'worker-execution-manifest', 'assignment_id': CASE.name,
        'runtime_manifest_sha256': sha(ROOT / runtime / 'SOURCE-MANIFEST.json'),
        'status': 'exception_1_cpu_draft_only', 'delivery_ready': False,
        'original_native_observed': False, 'cases': entries}
    put(OUT / 'manifest.json', manifest)
    return {'cases': len(entries), 'manifest_sha256': sha(OUT / 'manifest.json'),
            'construction_sha256': [row['construction_sha256'] for row in entries]}


if __name__ == '__main__':
    print(json.dumps(build(), sort_keys=True))
