"""Check the diagnostic official-versus-emergency contrast holds motion fixed."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(official_context=None):
    emergency = HERE / 'current-fixture/controlled_1'
    official = HERE / 'current-fixture/official_approach'
    fixed = ('road.xodr', 'video_frames.jsonl', 'vehicle_poses.jsonl', 'trace.jsonl',
             'capture/evidence.jsonl', 'capture/native/frames.jsonl')
    if any(sha(emergency / name) != sha(official / name) for name in fixed):
        raise ValueError('Official comparison changed road, bodies, lights, response or frame join')
    first = json.loads((emergency / 'emergency_context.json').read_text())
    second = (official_context if official_context is not None else
              json.loads((official / 'emergency_context.json').read_text()))
    if (first.get('emergency_vehicle_authorized') is not True or
            second.get('responding_vehicle_kind') != 'regulatory_agency_official' or
            second.get('official_vehicle_reviewed') is not True or
            not second.get('official_regulatory_agency_source') or
            second.get('emergency_vehicle_authorized') is not None):
        raise ValueError('Source-vehicle identity contrast is not source-bound')
    for name in ('ego_actor_id', 'emergency_actor_id', 'qualifying_flash_equipment_reviewed',
                 'officer_directed_otherwise', 'qualifying_flash_equipment_source',
                 'flashing_light_visual_source', 'visibility_review_source'):
        if first.get(name) != second.get(name):
            raise ValueError('Official comparison changed fixed reviewed condition: ' + name)
    return {'format': 'c405647-2f-official-comparison-audit-v1',
            'comparison_id': HERE.name + '__official_kind_comparison',
            'case_ids': [HERE.name + '__controlled_1', HERE.name + '__official_approach'],
            'fixed_source_sha256': {name: sha(emergency / name) for name in fixed},
            'deliberate_difference': 'reviewed source vehicle kind: authorized emergency versus regulatory-agency official',
            'diagnostic_only': True, 'original_native_observed': False,
            'legal_verdict': None}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--negative', action='store_true')
    args = parser.parse_args()
    if args.negative:
        context = json.loads((HERE / 'current-fixture/official_approach/emergency_context.json').read_text())
        context['official_vehicle_reviewed'] = False
        print(json.dumps(audit(context), indent=2))
    else:
        print(json.dumps(audit(), indent=2))
