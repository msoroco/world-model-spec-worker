"""Audit a three-point following-gap sweep against sealed original Native histories.

The output describes engineering measurements only. It makes no legal finding.
Synthetic captures may be exercised with --diagnostic-selftest but cannot pass
the Native realization gate.
"""
import argparse
import hashlib
import json
import shutil
from pathlib import Path

from following_measurements import analyze

GAPS = (7.0, 8.5, 10.0)
FIXED = ('native_map_id', 'highway_id', 'road_id', 'following_lane_id',
         'target_lane_id', 'hill_crest_source', 'lane_geometry_source',
         'surface_source', 'traffic_source', 'route_source', 'following_forward_xy')
FIXED_COMMANDS = ('ego_target_speed_mps', 'lead_target_speed_mps',
                  'minimum_corridor_length_m', 'minimum_crest_rise_m',
                  'rate_hz', 'duration_s')
SEALED = ('config.json', 'vehicle_history.jsonl',
          'video_frames.jsonl', 'trace.jsonl')
PACKAGE = Path(__file__).resolve().parent
REPO = PACKAGE.parent.parent


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def audit_point(root, requested_gap, *, diagnostic_selftest=False):
    root = Path(root)
    config = read(root/'config.json')
    result = read(root/'result.json')
    seal = read(root/'capture-seal.json')
    provenance = 'synthetic_fixture' if diagnostic_selftest else 'native'
    if (seal.get('format') != 'worker-sealed-capture' or
            seal.get('provenance_kind') != provenance or
            seal.get('diagnostic_fixture') is not diagnostic_selftest or
            result.get('provenance_kind') != provenance or
            result.get('diagnostic_fixture') is not diagnostic_selftest):
        raise ValueError('Original Native provenance required')
    if not set(SEALED) <= set(seal.get('sources', {})):
        raise ValueError('Sweep source absent from capture seal')
    for name in SEALED:
        if digest(root/name) != seal['sources'][name]:
            raise ValueError('Sweep source differs from capture seal: '+name)
    if config.get('requested_engineering_gap_m') != requested_gap:
        raise ValueError('Selected engineering gap differs from sweep point')
    if config.get('rate_hz') != 20 or config.get('duration_s') != 45 or seal.get('frames') != 900:
        raise ValueError('Sweep capture duration differs from 900-frame plan')
    if result.get('case_id') != config.get('selected_case_id'):
        raise ValueError('Result case differs from selected construction')
    observation = analyze(root)
    samples = observation['samples']
    if len(samples) != 900:
        raise ValueError('Original following measurements omit planned frames')
    change = observation['first_lane_change']['time_s']
    before = [s for s in samples if s['time_s'] < change]
    following = [s for s in before if s['following']]
    if len(following) < 20:
        raise ValueError('Too little original following before lane change')
    if {s['surface_condition'] for s in before} != {'dry'}:
        raise ValueError('Sweep surface condition differs')
    if any(s['lead_brake'] for s in before):
        raise ValueError('Sweep lead braking differs')
    if len({tuple(s['traffic_actor_ids']) for s in before}) != 1:
        raise ValueError('Sweep traffic inventory changed')
    context = read(root/'road_context.json')
    return {'requested_engineering_gap_m': requested_gap,
            'case_id': result['case_id'], 'source_root': str(root),
            'source_sha256': {name:digest(root/name) for name in (*SEALED, 'road_context.json')},
            'capture_seal_sha256': digest(root/'capture-seal.json'),
            'frames':len(samples), 'pre_change_following_frames':len(following),
            'first_lane_change':observation['first_lane_change'],
            'minimum_pre_change_body_gap_m':min(s['longitudinal_body_gap_m'] for s in following),
            'mean_pre_change_body_gap_m':sum(s['longitudinal_body_gap_m'] for s in following)/len(following),
            'first_pre_change_body_gap_m':following[0]['longitudinal_body_gap_m'],
            'last_pre_change_body_gap_m':following[-1]['longitudinal_body_gap_m'],
            'mean_ego_speed_mps':sum(s['ego_speed_mps'] for s in following)/len(following),
            'mean_lead_speed_mps':sum(s['lead_speed_mps'] for s in following)/len(following),
            'traffic_actor_ids':before[0]['traffic_actor_ids'],
            'fixed_commands':{key:config[key] for key in FIXED_COMMANDS},
            'fixed_context':{key:context[key] for key in FIXED}}


def audit_grid(roots, *, diagnostic_selftest=False):
    if len(roots) != len(GAPS) or len({str(Path(x).resolve()) for x in roots}) != len(GAPS):
        raise ValueError('Three distinct sweep captures required')
    points = [audit_point(root, gap, diagnostic_selftest=diagnostic_selftest)
              for root,gap in zip(roots,GAPS)]
    base = points[0]
    if any(p['fixed_context'] != base['fixed_context'] for p in points[1:]):
        raise ValueError('Sweep road context changed between points')
    if any(p['fixed_commands'] != base['fixed_commands'] for p in points[1:]):
        raise ValueError('Sweep controller conditions changed between points')
    if any(len(p['traffic_actor_ids']) != len(base['traffic_actor_ids']) for p in points[1:]):
        raise ValueError('Sweep traffic participant count changed between points')
    if len({p['case_id'] for p in points}) != 3:
        raise ValueError('Sweep cases are not distinct')
    return {'format':'c101303-original-following-sweep-audit',
            'native_realization_passed':not diagnostic_selftest,
            'diagnostic_only':diagnostic_selftest,
            'legal_conclusion':'unresolved', 'legal_threshold_asserted':False,
            'points':points}


def build_diagnostic_grid(output_root):
    """Exercise the positive checker path with explicit synthetic projections.

    The supplied short diagnostic histories change lanes after seven following
    frames. This makes a *new* synthetic 40-frame following interval for each
    selected point; it never alters or replaces the retained original fixture.
    """
    output_root = Path(output_root).resolve()
    if output_root.exists():
        raise ValueError('Diagnostic projection output already exists')
    if REPO / '.runtime-work' not in output_root.parents:
        raise ValueError('Diagnostic projections must remain under ignored .runtime-work')
    source_root = REPO / '.runtime-work/c101303-full-duration'
    labels = ('closer', 'midpoint', 'base')
    roots = []
    for label in labels:
        source = source_root / (label + '-positive-v1/attempt')
        target = output_root / label
        target.mkdir(parents=True)
        for name in (*SEALED, 'result.json', 'road_context.json'):
            shutil.copy2(source / name, target / name)
        original = [json.loads(line) for line in (target / 'vehicle_history.jsonl').read_text().splitlines()]
        if (len(original) != 900 or
                sum(not row['lane_change_started'] for row in original) != 7):
            raise ValueError('Expected short original diagnostic history changed: ' + label)
        template = original[6]
        if template['lane_change_started'] or template['ego']['lane_id'] != template['lead']['lane_id']:
            raise ValueError('Pre-change following template missing: ' + label)
        for i in range(7, 40):
            projected = json.loads(json.dumps(template))
            projected['frame'] = original[i]['frame']
            projected['time_s'] = original[i]['time_s']
            original[i] = projected
        original_brake_frames = [i for i, row in enumerate(original[:40])
                                 if row['lead'].get('brake_applied')]
        for row in original[:40]:
            row['lead']['brake_applied'] = False
        (target / 'vehicle_history.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in original))
        source_seal = json.loads((source / 'capture-seal.json').read_text())
        if (source_seal.get('provenance_kind') != 'synthetic_fixture' or
                source_seal.get('diagnostic_fixture') is not True):
            raise ValueError('Original source is not an explicit diagnostic fixture')
        seal = {'format': 'worker-sealed-capture',
                'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
                'projection_kind': 'extended_pre_change_following_cpu_selftest',
                'frames': 900, 'physical_acceptance_claimed': False,
                'sources': {name: digest(target / name) for name in (*SEALED, 'road_context.json')},
                'source_attempt': str(source.relative_to(REPO)),
                'source_capture_seal_sha256': digest(source / 'capture-seal.json'),
                'synthetic_modifications': {'held_following_through_index': 39,
                                            'removed_lead_brake_indices': original_brake_frames}}
        (target / 'capture-seal.json').write_text(json.dumps(seal, indent=2) + '\n')
        roots.append(target)
    receipt = audit_grid(roots, diagnostic_selftest=True)
    if (receipt['native_realization_passed'] or not receipt['diagnostic_only'] or
            receipt['legal_threshold_asserted']):
        raise AssertionError('Synthetic projection escaped diagnostic boundary')
    (output_root / 'diagnostic-sweep-audit.json').write_text(json.dumps(receipt, indent=2) + '\n')
    return receipt


def main():
    parser = argparse.ArgumentParser()
    for name in ('gap7', 'gap8_5', 'gap10'):
        parser.add_argument('--'+name.replace('_','-'), type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--diagnostic-selftest', action='store_true')
    parser.add_argument('--build-diagnostic-grid', type=Path)
    args = parser.parse_args()
    if args.build_diagnostic_grid:
        if any((args.gap7, args.gap8_5, args.gap10, args.output)):
            parser.error('Projection builder takes only --build-diagnostic-grid')
        receipt = build_diagnostic_grid(args.build_diagnostic_grid)
        print(json.dumps({'diagnostic_only': receipt['diagnostic_only'],
                          'points': len(receipt['points']),
                          'following_frames': [p['pre_change_following_frames'] for p in receipt['points']]}))
        return
    if not all((args.gap7, args.gap8_5, args.gap10, args.output)):
        parser.error('The three original sweep attempts and --output are required')
    value = audit_grid((args.gap7, args.gap8_5, args.gap10),
                       diagnostic_selftest=args.diagnostic_selftest)
    args.output.write_text(json.dumps(value, indent=2)+'\n')


if __name__ == '__main__':
    main()
