"""Materialize reproducible C405647 CPU-only saved motion packets."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'native'))
from geometry import CASES, requested_tracks
from measure_saved import measure


def build():
    root = ROOT / 'synthetic-local'
    root.mkdir(exist_ok=True)
    results = []
    for case in CASES:
        folder = root / case
        folder.mkdir(exist_ok=True)
        scope = json.loads((ROOT / 'native/source-scope.json').read_text())
        scope['case_suffix'] = case
        (folder / 'source-scope.json').write_text(json.dumps(scope, sort_keys=True) + '\n')
        rows = []
        for request in requested_tracks(case):
            rows.append({'frame': request['frame'], 'time_s': request['time_s'],
                         'subject': request['subject_request'],
                         'approach': request['approach_request'],
                         'front_red_flash_on': request['lamp_request']['front_red_flash_on'],
                         'source_kind': 'synthetic_cpu'})
        (folder / 'actor-frames.jsonl').write_text(''.join(
            json.dumps(row, sort_keys=True) + '\n' for row in rows))
        report = measure(folder)
        (folder / 'analysis-report.json').write_text(json.dumps(report, indent=2) + '\n')
        results.append({'case_suffix': case, 'frames': len(rows),
                        'catchup_frame': report['catchup_frame'],
                        'clearance_frame': report['first_full_body_inner_lane_clearance_frame']})
    return {'passed': True, 'cases': results,
            'scope': 'retained synthetic CPU motion packets; no Native observations'}


if __name__ == '__main__':
    print(json.dumps(build(), indent=2))
