"""Audit source-bound speed readbacks and saved CPU receipts for exact drafts."""

import hashlib
import json
from pathlib import Path
from statistics import median

from through_speed_sweep import TARGETS_MPS, body_speed_samples

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def main():
    manifest = json.loads((ROOT / 'through-speed-compatibility-manifest.json').read_text())
    receipts = []
    fixed_ego = None
    for target, entry in zip(TARGETS_MPS, manifest['cases']):
        speed = int(target)
        case_id = ROOT.name + f'__yield_nearest_view_through_speed_{speed}'
        assert entry['case_id'] == case_id
        recipe_path = REPO / entry['fixture_recipe']
        recipe = json.loads(recipe_path.read_text())
        for item in recipe['sources']:
            assert sha(REPO / item['source']) == item['sha256']
        assert sha(REPO / recipe['generator']['source']) == recipe['generator']['sha256']
        source = ROOT / f'cases/through_speed_{speed}/diagnostic-sources'
        interactions = rows(source / 'interaction_history.jsonl')
        assert len(interactions) == 600
        measured = body_speed_samples(interactions)
        first_speed = median(row['through_vehicle_speed_mps'] for row in measured[:50])
        assert abs(first_speed - target) < 1e-8
        ego = [row['ego'] for row in interactions]
        if fixed_ego is None:
            fixed_ego = ego
        else:
            assert ego == fixed_ego
        compat = REPO / f'.runtime-work/c158190-through-speed-{speed}-compat-v2'
        positive = json.loads((compat / 'compatibility.json').read_text())
        assert positive['passed'] is True and positive['case_id'] == case_id
        assert positive['construction_sha256'] == entry['construction_sha256']
        channel = rows(compat / 'channels/through_vehicle_speed.jsonl')
        assert len(channel) == 600
        assert abs(channel[1]['value']['speed_mps'] - target) < 1e-8
        saved = REPO / f'.runtime-work/c158190-through-speed-{speed}-saved-v1/v0001'
        processing = json.loads((saved / 'processing.json').read_text())
        assert processing['passed'] is True and processing['case_id'] == case_id
        assert processing['recorded_only'] is True and processing['originals_preserved'] is True
        assert processing['physical_acceptance_claimed'] is False
        assert processing['legal_acceptance_claimed'] is False
        saved_channel = rows(saved / 'analysis/channels/through_vehicle_speed.jsonl')
        assert len(saved_channel) == 600
        assert abs(saved_channel[1]['value']['speed_mps'] - target) < 1e-8
        receipts.append({'case_id': case_id, 'commanded_target_mps': target,
                         'synthetic_body_speed_first_50_median_mps': first_speed,
                         'source_interaction_sha256': sha(source / 'interaction_history.jsonl'),
                         'compatibility_sha256': sha(compat / 'compatibility.json'),
                         'saved_processing_sha256': sha(saved / 'processing.json'),
                         'original_frame_count': 600})
    report = {'format': 'c158190-through-speed-source-saved-proof',
              'cases': receipts, 'fixed_ego_body_histories': True,
              'source_kind': 'synthetic compatibility diagnostic',
              'native_feasibility_proven': False,
              'original_pixels_reviewed': False,
              'legal_hazard_cutoff_claimed': False}
    (ROOT / 'through-speed-saved-proof.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'passed': True, 'cases': 3, 'recorded_only_saved': True}))


if __name__ == '__main__':
    main()
