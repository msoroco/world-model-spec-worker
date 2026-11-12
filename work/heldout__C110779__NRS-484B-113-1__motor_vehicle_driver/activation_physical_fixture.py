"""Source-shaped completion protocol for the forward-only activation control."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'runtime/scenario_pipeline'))
from worker_exchange.fixture_recipe import materialize
from backing_safety_measurement import measure


def run(case_id, kind):
    if not case_id.endswith('__no_reverse_control'):
        raise ValueError('Only the forward-only control is supported')
    if kind not in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
        raise ValueError('Unknown physical fixture kind')
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    entry = next(e for e in manifest['cases'] if e['case_id'] == case_id)
    with TemporaryDirectory(prefix='forward-control-', dir=ROOT / '.runtime-work') as temp:
        root = Path(temp) / 'fixture'
        materialize(ROOT, ROOT / entry['fixture_recipe'], root)
        motion = root / 'backing_motion.jsonl'
        contacts = root / 'backing_contacts.jsonl'
        context = root / 'backing_context.json'
        if kind == 'missing_evidence':
            motion.unlink()
        elif kind == 'incomplete_motion':
            rows = [json.loads(line) for line in motion.read_text().splitlines() if line]
            for row in rows:
                row['ego_velocity_xy'] = [0.0, 0.0]
            motion.write_text(''.join(json.dumps(row) + '\n' for row in rows))
        sources = {p.name: sha256(p.read_bytes()).hexdigest()
                   for p in (motion, contacts, context) if p.is_file()}
        if kind == 'missing_evidence':
            try:
                measure(motion, contacts, context)
            except ValueError as error:
                if 'Missing original source: backing_motion.jsonl' not in str(error):
                    raise
            else:
                raise ValueError('Missing original motion was accepted')
            status, frames = 'unverified', []
        else:
            rows = [json.loads(line) for line in motion.read_text().splitlines() if line]
            measured = measure(motion, contacts, context)
            if measured['backing_onset_frame'] is not None:
                raise ValueError('Forward-only control contains reverse movement')
            forward = [row['frame'] for row in rows if
                       sum(a*b for a, b in zip(row['ego_heading_xy'], row['ego_velocity_xy'])) > 0]
            status = 'met' if len(rows) >= 2 and len(forward) == len(rows) else 'not_met'
            frames = forward if status == 'met' else []
        expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                    'missing_evidence': 'unverified'}[kind]
        if status != expected:
            raise ValueError('Unexpected forward-only control status: ' + status)
        return {'case_id': case_id, 'fixture_kind': kind, 'diagnostic_fixture': True,
                'actual_native_capture': False,
                'physical_checks': {'maneuver': {'status': status,
                    'method': 'original 20 Hz heading dot velocity, forward-only control with no reverse interval',
                    'sources': sources,
                    'missing_evidence': ['backing_motion.jsonl'] if status == 'unverified' else []}},
                'maneuver_completed': status == 'met',
                'realized_observables': {'forward_frame_ids': frames, 'backing_onset_frame': None}
                    if status == 'met' else {},
                'provenance_kind': 'native',
                'provenance_note': 'Native-shaped synthetic source protocol only',
                'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--kind', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = run(args.case, args.kind)
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
    print(args.case, args.kind, result['physical_checks']['maneuver']['status'], 'synthetic_fixture_only')
