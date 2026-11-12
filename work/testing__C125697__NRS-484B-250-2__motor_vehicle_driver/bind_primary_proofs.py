"""Bind current first-case CPU receipts without implying full case coverage."""
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
CASE = 'testing__C125697__NRS-484B-250-2__motor_vehicle_driver__off_ego_left_near_time'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bind():
    manifest_path = HERE/'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    entry = next(item for item in manifest['cases'] if item['case_id'] == CASE)
    construction = sha(HERE/entry['construction'])
    if construction != entry['construction_sha256']:
        raise ValueError('Construction changed since exact proof')
    offline = HERE/'primary-offline-v4.log'
    if not offline.is_file() or 'offline_passed": true' not in offline.read_text():
        raise ValueError('Exact offline proof missing')
    receipt_path = HERE/'primary-compatibility-receipt.json'
    receipt = json.loads(receipt_path.read_text())
    if (receipt.get('case_id') != CASE or receipt.get('candidate_id') != 'primary'
            or receipt.get('construction_sha256') != construction
            or receipt.get('passed') is not True):
        raise ValueError('Primary compatibility receipt differs')
    entry['offline'] = {
        'command': '.venv-cpu/bin/python runtime.py offline --manifest '
                   'work/testing__C125697__NRS-484B-250-2__motor_vehicle_driver/execution-manifest.json '
                   '--case '+CASE+' --output .runtime-work/c125697-primary-offline-v4',
        'exit_code': 0, 'construction_sha256': construction,
        'log': offline.name, 'log_sha256': sha(offline),
    }
    entry['compatibility'] = {
        'receipt': receipt_path.name, 'sha256': sha(receipt_path),
        'log': 'primary-compatibility-analysis.log',
    }
    entry['negative'] = {'log': 'primary-negative-analysis.log'}
    sources = {
        'ru.subject': ('capture_sources.py', 'original actor identity', 'capture/evidence.jsonl'),
        'ru.motor_vehicle': ('capture_sources.py', 'Native vehicle blueprint', 'capture/evidence.jsonl'),
        'kin.position': ('capture_sources.py', 'original actor pose', 'trace.jsonl'),
        'kin.velocity': ('capture_sources.py', 'original actor velocity', 'trace.jsonl'),
        'kin.speed': ('capture_sources.py', 'original actor speed magnitude', 'trace.jsonl'),
        'st.intersection': ('site_packet.py', 'source-bound crossing polygon', 'junction_context.json'),
        'rel.bearing': ('simultaneous_entries.py', 'source approach projection', 'junction_context.json'),
        'entry_timing': ('finalizer.py', 'original body/frame join', 'crossing_history.jsonl'),
        'entry_context': ('finalizer.py', 'source crossing context', 'junction_context.json'),
    }
    entry['acquisition'] = {key: {'entrypoint': source, 'method': method, 'evidence': evidence}
                            for key, (source, method, evidence) in sources.items()}
    manifest_path.write_text(json.dumps(manifest, indent=2)+'\n')
    return {'case_id': CASE, 'construction_sha256': construction,
            'offline_log_sha256': sha(offline),
            'compatibility_receipt_sha256': sha(receipt_path),
            'negative_log_sha256': sha(HERE/'primary-negative-analysis.log')}


if __name__ == '__main__':
    print(json.dumps(bind(), indent=2))
