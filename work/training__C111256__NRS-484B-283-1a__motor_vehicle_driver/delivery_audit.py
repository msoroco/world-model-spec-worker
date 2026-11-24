"""Independent source audit; diagnostic fixtures cannot become accepted delivery."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
CHECKS = ('native_source', 'all_participants', 'time_join', 'full_video_decode',
          'actual_pixels', 'physical_completion')
SOURCES = ('native_samples.jsonl', 'video_frames.jsonl', 'road_geometry.json',
           'capture/manifest.json', 'capture/evidence.jsonl', 'trace.jsonl',
           'body_history.jsonl', *(name + '.mkv' for name in CAMERAS))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def audit(case, candidate, attempt, processing, diagnostic):
    manifest = read(HERE / 'execution-manifest.json')
    entry = next((x for x in manifest['cases'] if x['case_id'] == case), None)
    if entry is None:
        raise ValueError('Unselected delivery case')
    selected = entry if candidate == 'primary' else next((x for x in entry['candidates'] if x['id'] == candidate), None)
    if selected is None or sha(HERE / selected['construction']) != selected['construction_sha256']:
        raise ValueError('Selected construction changed')
    selection = read(attempt / 'candidate-selection.json')
    if selection['candidate_id'] != candidate or selection['construction_sha256'] != selected['construction_sha256']:
        raise ValueError('Candidate selection differs')
    receipt = read(processing)
    if not (receipt['passed'] and receipt['recorded_only'] and receipt['originals_preserved']
            and receipt['timestamp_joins'] == {'frames': 600, 'passed': True, 'missing_original_trace_or_map': False}
            and receipt['final_video_checks']['passed'] and not receipt['missing_evidence']
            and receipt['case_id'] == case and receipt['candidate_id'] == candidate
            and not receipt['physical_acceptance_claimed'] and not receipt['legal_acceptance_claimed']):
        raise ValueError('Saved source proof incomplete')
    hashes = {}
    for name in SOURCES:
        path = attempt / name
        if not path.is_file():
            raise ValueError('Missing original source: ' + name)
        hashes[name] = sha(path)
        if receipt['original_source_hashes'].get(name) != hashes[name]:
            raise ValueError('Saved original source changed: ' + name)
    rows = [json.loads(line) for line in (attempt / 'native_samples.jsonl').read_text().splitlines()]
    maps = [json.loads(line) for line in (attempt / 'video_frames.jsonl').read_text().splitlines()]
    if len(rows) != len(maps) or len(rows) != 600:
        raise ValueError('Original source frame join differs')
    result_path = Path(receipt['result'])
    if not result_path.is_file() or sha(result_path) != receipt['result_sha256']:
        raise ValueError('Saved result changed')
    result = read(result_path)
    if result['case_id'] != case or result.get('accepted') or result.get('legal_verdict_claimed'):
        raise ValueError('Saved result identity or acceptance differs')
    source_kind = read(attempt / 'capture/manifest.json').get('source_kind')
    if diagnostic:
        return {'format': 'c111256-delivery-audit', 'case_id': case,
                'candidate_id': candidate, 'diagnostic_only': True, 'accepted': False,
                'checks': {key: key in ('all_participants', 'time_join', 'full_video_decode') for key in CHECKS},
                'source_kind': source_kind, 'original_source_sha256': hashes,
                'original_native_verified': False, 'actual_pixels_verified': False}
    if source_kind != 'original_native' or selection.get('manifest_sha256') != sha(HERE / 'execution-manifest.json'):
        raise ValueError('Original Native source required')
    review = attempt / 'independent-physical-review.json'
    if not review.is_file() or read(review).get('passed') is not True:
        raise ValueError('Independent physical and pixel review required')
    return {'format': 'c111256-delivery-audit', 'case_id': case,
            'candidate_id': candidate, 'accepted': True,
            'checks': {key: True for key in CHECKS}, 'original_source_sha256': hashes}


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    for name in ('case', 'candidate', 'attempt', 'processing', 'output'):
        p.add_argument('--' + name, required=True)
    p.add_argument('--diagnostic', action='store_true')
    a = p.parse_args()
    value = audit(a.case, a.candidate, Path(a.attempt), Path(a.processing), a.diagnostic)
    target = Path(a.output)
    if target.exists():
        raise ValueError('Retain previous audit output')
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value, indent=2) + '\n')
    print(json.dumps({'case_id': a.case, 'diagnostic_only': a.diagnostic, 'accepted': value['accepted']}))
