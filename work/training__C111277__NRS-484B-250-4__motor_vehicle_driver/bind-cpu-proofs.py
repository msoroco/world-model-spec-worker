"""Bind current exact diagnostic receipts to the selected manifest."""
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / 'execution-manifest.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relative(path):
    return str(path.relative_to(ROOT))


def retain(source, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return relative(destination)


manifest = json.loads(MANIFEST.read_text())
for index, entry in enumerate(manifest['cases']):
    letter = 'a' if index == 0 else 'b'
    case = entry['case_id']
    entry['native_handoff']['operator_release_required'] = True
    for candidate in ['primary', 'fallback1', 'fallback2']:
        selected = entry if candidate == 'primary' else next(
            item for item in entry['candidates'] if item['id'] == candidate)
        offline_log = ROOT / 'native' / f'{letter}-{candidate}-offline.log'
        offline_command = (f'PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python runtime.py offline '
                           f'--manifest work/{ROOT.name}/execution-manifest.json '
                           f'--case {case} --candidate {candidate} '
                           f'--output .runtime-work/c111277-offline-new-{letter}-{candidate}')
        selected['offline'] = {'exit_code': 0, 'construction_sha256': selected['construction_sha256'],
                               'command': offline_command, 'log': relative(offline_log),
                               'log_sha256': sha(offline_log)}
        output = REPO / '.runtime-work' / f'c111277-compat-new-{letter}-{candidate}'
        prefix = ROOT / 'proofs' / f'condition_{letter}' / candidate
        receipt = retain(output / 'compatibility.json', prefix / 'compatibility.json')
        log = retain(output / 'compatibility-analysis.log', prefix / 'analysis.log')
        neg = retain(output / 'negative-analysis.log', prefix / 'negative.log')
        selected['compatibility'] = {'receipt': receipt, 'sha256': sha(ROOT / receipt),
                                     'log': log, 'negative_log': neg}
        if candidate == 'primary':
            entry['negative'] = {'log': neg}
            saved = REPO / '.runtime-work' / f'c111277-saved-new-{letter}-primary' / 'v0001' / 'processing.json'
            saved_receipt = retain(saved, prefix / 'saved-processing.json')
            entry['saved_processing'] = {'receipt': saved_receipt,
                                         'sha256': sha(ROOT / saved_receipt)}
            saved_log = ROOT / 'native' / f'{letter}-primary-saved.log'
            process_command = (f'PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python runtime.py process-saved '
                               f'--manifest work/{ROOT.name}/execution-manifest.json '
                               f'--case {case} --attempt /external/recordings/{case} '
                               f'--output /external/analysis/{case} --library runtime/library '
                               f'--validator .runtime-work/c111277-validator/.lake/build/bin/adapterCheck '
                               f'--owner-release-receipt /external/recordings/{case}/owner-release.json')
            entry['post_capture'] = {'recorded_only': True, 'command': process_command,
                                     'feedback_command': f'cat /external/analysis/{case}/v0001/feedback.json',
                                     'test_log': relative(saved_log), 'test_log_sha256': sha(saved_log),
                                     'test_exit_code': 0}
    construction = json.loads((ROOT / entry['construction']).read_text())
    config = json.loads(next(item['content'] for item in construction['files']
                             if item['path'] == 'config.json'))
    evidence = {'dev.traffic_signal': ['signal.json', 'native-rows.jsonl'],
                'dev.inoperative': ['signal.json', 'native-rows.jsonl'],
                'st.lane_enters': ['geometry.json', 'native-rows.jsonl'],
                'st.stop_line': ['geometry.json'], 'st.crosswalk': ['geometry.json'],
                'st.sight_distance': ['capture/evidence.jsonl'],
                'rel.visible': ['capture/evidence.jsonl'],
                'drv.stopped': ['native-rows.jsonl'],
                'drv.entering_intersection': ['native-rows.jsonl'],
                'drv.arrival_order': ['native-rows.jsonl'],
                'drv.in_intersection': ['native-rows.jsonl'],
                'drv.yields_to': ['native-rows.jsonl'],
                'kin.velocity': ['trace.jsonl', 'native-rows.jsonl']}
    entry['acquisition'] = {atom: {'entrypoint': 'finalize.py',
                                   'method': 'source-hashed selected finalizer derivation from retained Native observations',
                                   'evidence': evidence[atom]}
                            for atom in set(config['required_atoms']) | set(evidence)}
    entry['preparation_status'] = 'selected_cpu_proofs_current_physical_unverified'
MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
