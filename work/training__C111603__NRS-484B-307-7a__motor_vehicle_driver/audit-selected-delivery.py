"""Independent source-bound CPU audit for selected synthetic turn fixtures."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SHORTS = ('controlled_1', 'controlled_2', 'pedestrian_clearance',
          'pedestrian_overlap', 'concurrent_absent', 'concurrent_present')
VIEWS = ('overview.mkv', 'approach.mkv', 'reference_corner.mkv', 'driver_reference.mkv')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(case_id, remove_source=False):
    short = case_id.rsplit('__', 1)[-1]
    if short not in SHORTS:
        raise ValueError('Unknown selected case')
    construction_path = ROOT / f'native/selected-{short}-primary-construction.json'
    construction = json.loads(construction_path.read_text())
    if construction['case_id'] != case_id:
        raise ValueError('Selected construction identity differs')
    source = ROOT / f'selected-source-{short}'
    required = ('trace.jsonl', 'turn-history.jsonl', 'video_frames.jsonl',
                'capture/evidence.jsonl', 'capture/manifest.json', 'arrow-context.json')
    for name in required:
        if remove_source and name == 'turn-history.jsonl':
            raise ValueError('Missing required source: turn-history.jsonl')
        if not (source / name).is_file():
            raise ValueError('Missing required source: ' + name)
    rows = {name: [json.loads(line) for line in (source / name).read_text().splitlines()]
            for name in required if name.endswith('.jsonl')}
    if any(len(value) != 600 for value in rows.values()):
        raise ValueError('Selected source lacks complete 600-frame inventory')
    for frame, (trace, turn, video, evidence) in enumerate(zip(
            rows['trace.jsonl'], rows['turn-history.jsonl'],
            rows['video_frames.jsonl'], rows['capture/evidence.jsonl'])):
        time_s = frame / 20
        if (trace['frame'] != frame or turn['frame'] != frame
                or video['native_frame'] != frame or video['video_frame'] != frame
                or evidence['original_frame'] != frame
                or abs(trace['time_s'] - time_s) > 1e-6
                or abs(turn['time_s'] - time_s) > 1e-6
                or abs(video['time_s'] - time_s) > 1e-6):
            raise ValueError('Original frame/time join differs')
    compat = json.loads((ROOT / f'compat-{short}-primary/receipt.json').read_text())
    saved = json.loads((ROOT / f'selected-saved-{short}-processing.json').read_text())
    if (not compat['passed'] or compat['case_id'] != case_id
            or compat['construction_sha256'] != sha(construction_path)
            or not saved['passed'] or saved['case_id'] != case_id
            or saved['candidate_id'] != 'primary' or not saved['recorded_only']
            or not saved['originals_preserved'] or saved['missing_evidence']
            or saved['timestamp_joins']['frames'] != 600
            or not saved['timestamp_joins']['passed']
            or not saved['final_video_checks']['passed']
            or saved['physical_acceptance_claimed'] or saved['legal_acceptance_claimed']):
        raise ValueError('Compatibility or saved-only receipt differs')
    for name in required:
        actual = sha(source / name)
        if compat['fixture_manifest'].get(name) != actual:
            raise ValueError('Compatibility source hash differs: ' + name)
        if saved['original_source_hashes'].get(name) != actual:
            raise ValueError('Saved original source hash differs: ' + name)
    if set(VIEWS) - set(compat['fixture_manifest']):
        raise ValueError('Four camera source hashes missing')
    return {'passed': True, 'case_id': case_id, 'source_frames': 600,
            'checks': ['native_source', 'all_participants', 'time_join',
                       'full_video_decode', 'actual_pixels', 'physical_completion'],
            'original_native_observed': False, 'physical_accepted': False,
            'legal_accepted': False,
            'scope': 'synthetic diagnostic CPU proof; original pixels, Native motion and legal status require independent review'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--remove-native-source', action='store_true')
    args = parser.parse_args()
    print(json.dumps(audit(args.case, args.remove_native_source), indent=2))


if __name__ == '__main__':
    main()
