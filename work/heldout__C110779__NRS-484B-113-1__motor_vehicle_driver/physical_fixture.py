"""Source-shaped reverse-completion protocol fixtures; no physical acceptance."""
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
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    entry = next((x for x in manifest['cases'] if x['case_id'] == case_id), None)
    if entry is None or kind not in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
        raise ValueError('Unknown exact case or physical fixture kind')
    with TemporaryDirectory(prefix='backing-motion-', dir=ROOT / '.runtime-work') as temp:
        root = Path(temp) / 'fixture'
        materialize(ROOT, ROOT / entry['fixture_recipe'], root)
        motion = root / 'backing_motion.jsonl'
        contacts = root / 'backing_contacts.jsonl'
        context = root / 'backing_context.json'
        if kind == 'missing_evidence':
            motion.unlink()
        elif kind == 'incomplete_motion':
            rows = [json.loads(x) for x in motion.read_text().splitlines() if x.strip()]
            for row in rows:
                row['ego_velocity_xy'] = [0.0, 0.0]
            motion.write_text(''.join(json.dumps(x) + '\n' for x in rows))
        sources = {x.name: sha256(x.read_bytes()).hexdigest()
                   for x in (motion, contacts, context) if x.is_file()}
        if kind == 'missing_evidence':
            try:
                measure(motion, contacts, context)
            except ValueError as error:
                if 'Missing original source: backing_motion.jsonl' not in str(error):
                    raise
            else:
                raise ValueError('Missing original backing motion was accepted')
            observed, status = None, 'unverified'
        else:
            observed = measure(motion, contacts, context)
            status = 'met' if observed['backing_onset_frame'] is not None and observed['backing_end_frame'] > observed['backing_onset_frame'] else 'not_met'
        expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                    'missing_evidence': 'unverified'}[kind]
        if status != expected:
            raise ValueError('Unexpected source-derived backing fixture status: ' + status)
        return {'case_id': case_id, 'fixture_kind': kind, 'diagnostic_fixture': True,
                'actual_native_capture': False,
                'physical_checks': {'maneuver': {'status': status,
                    'method': 'original 20 Hz heading dot velocity and continuous reverse interval',
                    'sources': sources,
                    'missing_evidence': ['backing_motion.jsonl'] if observed is None else []}},
                'maneuver_completed': status == 'met',
                'realized_observables': {'backing_onset_frame': observed['backing_onset_frame'],
                                         'backing_end_frame': observed['backing_end_frame']}
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
