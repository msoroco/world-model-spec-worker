"""Test source-bound maneuver completion on three synthetic CPU motion outcomes."""
import argparse
import json
import os
from pathlib import Path
import shutil

from worker_exchange.native_output import physical_result

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
            'missing_evidence': 'unverified'}


def run(case_id, kind):
    if kind not in EXPECTED or case_id not in (ROOT.name + '__probe_a',
                                                ROOT.name + '__probe_b'):
        raise ValueError('Select an exact curbside case and outcome')
    output_root = Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT'])
    if '.runtime-work' not in output_root.parts:
        raise ValueError('Use ignored scratch under .runtime-work')
    label = case_id.rsplit('__', 1)[1]
    scratch = output_root / ('physical-' + label + '-' + kind)
    if scratch.exists():
        shutil.rmtree(scratch)
    scratch.mkdir(parents=True)
    config = json.loads((ROOT / 'draft-native' / label / 'primary/construction.json').read_text())
    config_text = next(item['content'] for item in config['files']
                       if item['path'] == 'config.json')
    (scratch / 'config.json').write_text(config_text)
    source = ROOT / 'compat-source' / label
    shutil.copyfile(source / 'video_frames.jsonl', scratch / 'video_frames.jsonl')
    if kind != 'missing_evidence':
        trace = [json.loads(row) for row in (source / 'trace.jsonl').read_text().splitlines()]
        if kind == 'incomplete_motion':
            for row in trace:
                row['position_m'] = [10, -1.75, 0.5]
                row['position'] = {'x': 10, 'y': -1.75, 'z': 0.5}
                row['speed_mps'] = 0
                row['speed_mph'] = 0
                row['velocity_mps'] = [0, 0, 0]
        (scratch / 'trace.jsonl').write_text(''.join(
            json.dumps(row, separators=(',', ':')) + '\n' for row in trace))
    result = physical_result(scratch, {
        'case_id': case_id,
        'target_checks': [{'target': 'source_join', 'requested': True,
                           'measured': True, 'method': 'source-bounded fixture check',
                           'tolerance': 0, 'matched': True,
                           'physical_cause_confirmed': False,
                           'cause_evidence': ['trace.jsonl', 'video_frames.jsonl']}],
        'physical_acceptance_claimed': False,
        'legal_acceptance_claimed': False,
    })
    status = result['physical_checks']['maneuver']['status']
    if status != EXPECTED[kind] or result['maneuver_completed'] != (kind == 'complete_motion'):
        raise AssertionError('Source-derived physical status differs: ' + status)
    if result['provenance_kind'] != 'synthetic_fixture' or result['diagnostic_fixture'] is not True:
        raise AssertionError('CPU outcome lost synthetic provenance')
    if kind == 'complete_motion' and not result['realized_observables']:
        raise AssertionError('Complete motion needs measured progress')
    if result['physical_acceptance_claimed'] is not False:
        raise AssertionError('CPU outcome cannot claim physical acceptance')
    destination = ROOT / 'physical-preparation' / label
    destination.mkdir(parents=True, exist_ok=True)
    result_path = destination / (kind + '-result.json')
    result_path.write_text(json.dumps(result, indent=2) + '\n')
    log = destination / (kind + '.log')
    log.write_text('PASS ' + case_id + ' ' + kind + ' source-derived maneuver ' + status + '\n')
    print(str(result_path))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--kind', required=True)
    args = parser.parse_args()
    run(args.case, args.kind)
