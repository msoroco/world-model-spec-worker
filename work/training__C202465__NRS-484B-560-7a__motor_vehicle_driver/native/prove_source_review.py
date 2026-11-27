"""Exercise the rail review gate with diagnostic source shapes and mutations."""
import hashlib
import json
import os
from pathlib import Path
import tempfile

from source_review import ROLES, load


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    root = Path(os.environ.get('TMPDIR', '.runtime-work')).resolve()
    road_hash = 'a' * 64
    with tempfile.TemporaryDirectory(dir=root, prefix='c202465-review-') as temporary:
        folder = Path(temporary)
        values = {
            'rail-geometry': {'crossing_kind': 'at_grade', 'entry_rail_x_m': 10.0,
                              'clearance_reference_rail_x_m': 12.0},
            'opposite-space': {'opposite_side_space_before_entry_m': 12.0,
                               'queue_actor_identity_reviewed': True},
            'undercarriage-grade': {'minimum_undercarriage_clearance_m': .35,
                                   'rail_grade_required_clearance_m': .20}}
        for role in ROLES:
            source = folder / (role + '.source.txt')
            source.write_text('diagnostic source shape only\n')
            row = {'role': role, 'road_sha256': road_hash,
                   'source_sha256': sha(source), 'review_status': 'independently_reviewed',
                   'provenance_kind': 'original_native', 'reviewer_id': 'synthetic_test_only',
                   **values[role]}
            (folder / (role + '.json')).write_text(json.dumps(row, indent=2) + '\n')
        if len(load(folder, road_hash)) != 3:
            raise AssertionError('Review source schema failed')
        rejected = []
        for mutation in ('missing_source', 'stale_road', 'unreviewed',
                         'reversed_rails', 'unknown_queue', 'missing_grade'):
            path = folder / ('rail-geometry.json' if mutation in
                             ('missing_source', 'stale_road', 'unreviewed', 'reversed_rails')
                             else 'opposite-space.json' if mutation == 'unknown_queue'
                             else 'undercarriage-grade.json')
            original = path.read_text()
            row = json.loads(original)
            if mutation == 'missing_source':
                source = folder / 'rail-geometry.source.txt'
                prior = source.read_text()
                source.unlink()
            elif mutation == 'stale_road':
                row['road_sha256'] = 'b' * 64
            elif mutation == 'unreviewed':
                row['review_status'] = 'pending'
            elif mutation == 'reversed_rails':
                row['clearance_reference_rail_x_m'] = 9.0
            elif mutation == 'unknown_queue':
                row['queue_actor_identity_reviewed'] = False
            else:
                row.pop('minimum_undercarriage_clearance_m')
            if mutation != 'missing_source':
                path.write_text(json.dumps(row, indent=2) + '\n')
            try:
                load(folder, road_hash)
            except ValueError:
                rejected.append(mutation)
            else:
                raise AssertionError('Unsourced rail review accepted: ' + mutation)
            path.write_text(original)
            if mutation == 'missing_source':
                source.write_text(prior)
    proof = {'format': 'c202465-rail-review-gate-cpu-v1',
             'source_schema_passed': True, 'negative_mutations_rejected': rejected,
             'diagnostic_only': True, 'original_review_observed': False,
             'review_gate_sha256': sha(Path(__file__).with_name('source_review.py'))}
    target = Path(__file__).with_name('source-review-proof.json')
    target.write_text(json.dumps(proof, indent=2) + '\n')
    print(json.dumps(proof))


if __name__ == '__main__':
    main()
