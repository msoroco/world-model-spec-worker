"""Exercise source-bound physical outcomes on explicit synthetic CPU fixtures."""
import argparse
import json
import os
from pathlib import Path
import shutil

from worker_exchange.native_output import physical_result

ROOT = Path(__file__).resolve().parent
KINDS = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
         'missing_evidence': 'unverified'}
SUFFIXES = ('below_100_ft', 'at_100_ft', 'above_100_ft',
            'below_300_ft', 'at_300_ft', 'above_300_ft')


def run(suffix, kind):
    if suffix not in SUFFIXES or kind not in KINDS:
        raise ValueError('Exact selected suffix and physical outcome required')
    scratch_root = Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT'])
    if '.runtime-work' not in scratch_root.parts:
        raise ValueError('Physical scratch must remain under .runtime-work')
    scratch = scratch_root / ('physical-' + suffix + '-' + kind)
    if scratch.exists():
        shutil.rmtree(scratch)
    scratch.mkdir(parents=True)
    entry = json.loads((ROOT / 'draft-selected-execution-manifest.json').read_text())
    selected = next(e for e in entry['cases'] if e['case_id'].endswith('__' + suffix))
    construction = json.loads((ROOT / selected['construction']).read_text())
    config_text = next(f['content'] for f in construction['files'] if f['path'] == 'config.json')
    (scratch / 'config.json').write_text(config_text)
    source = ROOT / 'current-v2-case-sources' / suffix
    for name in ('video_frames.jsonl', 'trace.jsonl'):
        shutil.copyfile(source / name, scratch / name)
    if kind != 'missing_evidence':
        rows = [json.loads(row) for row in (source / 'body_history.jsonl').read_text().splitlines()]
        for index, row in enumerate(rows):
            row['road_id'] = 1 if kind == 'incomplete_motion' or index < len(rows) // 2 else 3
        (scratch / 'body_history.jsonl').write_text(''.join(
            json.dumps(row, separators=(',', ':')) + '\n' for row in rows))
    case_id = construction['case_id']
    result = physical_result(scratch, {
        'case_id': case_id,
        'target_checks': [{'target': 'synthetic source join', 'requested': True,
                           'measured': True, 'method': 'source-bound CPU fixture',
                           'tolerance': 0, 'matched': True,
                           'physical_cause_confirmed': False,
                           'cause_evidence': ['trace.jsonl', 'video_frames.jsonl']}],
        'physical_acceptance_claimed': False,
        'legal_acceptance_claimed': False,
    })
    status = result['physical_checks']['maneuver']['status']
    if status != KINDS[kind] or result['maneuver_completed'] != (kind == 'complete_motion'):
        raise AssertionError('Source-derived physical status differs: ' + status)
    if result['provenance_kind'] != 'synthetic_fixture' or result['diagnostic_fixture'] is not True:
        raise AssertionError('CPU fixture lost synthetic provenance')
    if kind == 'complete_motion' and not result['realized_observables']:
        raise AssertionError('Complete motion needs measured observations')
    destination = ROOT / 'physical-preparation' / suffix
    destination.mkdir(parents=True, exist_ok=True)
    (destination / (kind + '-result.json')).write_text(json.dumps(result, indent=2) + '\n')
    print('PASS', case_id, kind, 'source-derived maneuver', status)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--suffix', required=True)
    parser.add_argument('--kind', required=True)
    args = parser.parse_args()
    run(args.suffix, args.kind)
