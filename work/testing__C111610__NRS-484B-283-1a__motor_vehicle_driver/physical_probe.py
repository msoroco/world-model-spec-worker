"""Exercise pinned physical classifications on explicit synthetic histories."""
import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
KINDS = ('complete_motion', 'incomplete_motion', 'missing_evidence')


def probe(case, kind, output):
    if kind not in KINDS:
        raise ValueError('unknown physical fixture')
    scratch = REPO / '.runtime-work' / 'c111610-283' / 'physical-tmp'
    outroot = Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT']).resolve()
    if REPO / '.runtime-work' not in outroot.parents:
        raise ValueError('runtime output must be under .runtime-work')
    scratch.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((ROOT / 'execution-manifest.json').read_text())
    entry = next(e for e in manifest['cases'] if e['case_id'] == case)
    suffix = case.rsplit('__', 1)[-1]
    fixture = REPO / '.runtime-work' / 'c111610-283' / ('saved-v1-fixture-' + suffix)
    construction = json.loads((ROOT / entry['construction']).read_text())
    config = next(f['content'] for f in construction['files'] if f['path'] == 'config.json')
    mapping = (fixture / 'video_frames.jsonl').read_text()
    frames = [json.loads(line) for line in mapping.splitlines()]
    with tempfile.TemporaryDirectory(dir=scratch) as temporary:
        attempt = Path(temporary)
        (attempt / 'config.json').write_text(config)
        (attempt / 'video_frames.jsonl').write_text(mapping)
        if kind != 'missing_evidence':
            rows = []
            for index, frame in enumerate(frames):
                x = 100.0 * index / (len(frames) - 1) if kind == 'complete_motion' else 0.0
                rows.append({'frame': frame['carla_frame'], 'time_s': frame['time_s'],
                             'position_m': [x, 0.0], 'heading_deg': 0.0})
            (attempt / 'trace.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in rows))
        sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
        from worker_exchange.native_output import physical_result
        result = physical_result(attempt, {'case_id': case, 'target_checks': []})
        expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                    'missing_evidence': 'unverified'}[kind]
        if result['physical_checks']['maneuver']['status'] != expected:
            raise ValueError('physical classification differs from fixture')
        result['fixture_kind'] = kind
        result['diagnostic_fixture'] = True
        result['provenance_kind'] = 'synthetic_fixture'
        result['legal_acceptance_claimed'] = False
        output = Path(output)
        if output.exists() or output.parent.resolve() != ROOT:
            raise ValueError('fresh result must be under exact assignment')
        output.write_text(json.dumps(result, indent=2) + '\n')
        return expected


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--kind', choices=KINDS, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(args.case, args.kind, probe(args.case, args.kind, args.output))
