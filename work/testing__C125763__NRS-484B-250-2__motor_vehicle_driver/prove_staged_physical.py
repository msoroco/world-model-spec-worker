"""Audit the four staged descriptor constructions against retained CPU attempts."""
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
from worker_exchange.native_output import physical_result  # noqa: E402


def main():
    for prefix in ('primary', 'right', 'separated', 'opposite'):
        manifest_name = ('physical-candidate-manifest.json' if prefix == 'primary'
                         else f'physical-{prefix}-manifest.json')
        manifest = json.loads((ROOT / manifest_name).read_text())
        entry = manifest['cases'][0]
        attempt = REPO / '.runtime-work' / f'c125763-physical-{prefix}-compat-v1'
        result = json.loads((attempt / 'result.json').read_text())
        checks = result['physical_checks']
        if ({key: checks[key]['status'] for key in ('setup', 'target', 'maneuver')} !=
                {'setup': 'met', 'target': 'met', 'maneuver': 'not_met'} or
                checks['maneuver']['details'].get('criterion') != 'intersection_clearance' or
                'crossing_history.jsonl' not in checks['maneuver']['sources'] or
                result.get('physical_acceptance_claimed') is not False):
            raise ValueError('Incorrect staged physical classification: ' + entry['case_id'])
        with tempfile.TemporaryDirectory(prefix='c125763-physical-source-negative-') as temp:
            broken = Path(temp)
            for name in ('config.json', 'video_frames.jsonl', 'trace.jsonl', 'site.json'):
                shutil.copyfile(attempt / name, broken / name)
            negative = physical_result(broken, {'target_checks': [{'matched': True}]})
            missing = negative['physical_checks']['maneuver']
            if (missing['status'] != 'unverified' or
                    'crossing_history.jsonl' not in missing['missing_evidence']):
                raise ValueError('Missing original body history was accepted: ' + entry['case_id'])
        print(json.dumps({'case_id': entry['case_id'], 'setup': 'met',
                          'selected_target': 'met', 'synthetic_maneuver': 'not_met',
                          'missing_body_history': 'unverified',
                          'physical_acceptance_claimed': False}, sort_keys=True))


if __name__ == '__main__':
    main()
