"""Synthetic original-footprint completion protocol for exact left-turn cases."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from turn_geometry import measure

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def run(case_id, kind):
    entries = json.loads((HERE / 'probe-compatibility-manifest.json').read_text())['cases']
    entry = next((item for item in entries if item['case_id'] == case_id), None)
    if entry is None or kind not in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
        raise ValueError('Unknown exact turn case or fixture kind')
    recipe = json.loads((ROOT / entry['fixture_recipe']).read_text())
    diagnostic = json.loads((ROOT / recipe['generator']['source']).read_text())['files']
    with TemporaryDirectory(dir=ROOT / '.runtime-work', prefix='c109705-physical-') as tmp:
        base = Path(tmp)
        for name in ('road_geometry.json', 'body_footprints.json'):
            (base / name).write_text(diagnostic[name])
        geometry, body = base / 'road_geometry.json', base / 'body_footprints.json'
        if kind == 'missing_evidence':
            body.unlink()
        elif kind == 'incomplete_motion':
            data = json.loads(body.read_text())
            data['frames'] = [row for row in data['frames'] if row['phase'] != 'leaving_intersection']
            body.write_text(json.dumps(data) + '\n')
        source_hashes = {name: digest(base / name) for name in
                         ('road_geometry.json', 'body_footprints.json') if (base / name).is_file()}
        observed = None
        if kind == 'complete_motion':
            observed = measure(geometry, body)
            status = 'met' if (observed['approach_frame_ids'] and
                               observed['departure_frame_ids']) else 'not_met'
        else:
            try:
                measure(geometry, body)
            except ValueError as error:
                expected = ('missing required geometry source' if kind == 'missing_evidence'
                            else 'approach and leaving-intersection phases absent or reversed')
                if expected not in str(error):
                    raise
            else:
                raise ValueError('Missing or incomplete turn source was accepted')
            status = 'unverified' if kind == 'missing_evidence' else 'not_met'
        if status != {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                      'missing_evidence': 'unverified'}[kind]:
            raise ValueError('Synthetic turn completion status differs')
        return {'case_id': case_id, 'fixture_kind': kind, 'fixture_only': True,
                'diagnostic_fixture': True, 'actual_native_capture': False,
                'physical_checks': {'maneuver': {'status': status,
                    'method': 'original source-shaped approach and departure body phases',
                    'sources': source_hashes,
                    'missing_evidence': ['body_footprints.json'] if kind == 'missing_evidence' else []}},
                'maneuver_completed': status == 'met',
                'realized_observables': ({'approach_frames': observed['approach_frame_ids'],
                                         'departure_frames': observed['departure_frame_ids']}
                                        if observed else {}),
                'provenance_kind': 'native',
                'provenance_note': 'Synthetic Native-shaped protocol only',
                'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--kind', required=True,
                        choices=('complete_motion', 'incomplete_motion', 'missing_evidence'))
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = run(args.case, args.kind)
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
    print(args.case, args.kind, result['physical_checks']['maneuver']['status'],
          'synthetic_fixture_only')


if __name__ == '__main__':
    main()
