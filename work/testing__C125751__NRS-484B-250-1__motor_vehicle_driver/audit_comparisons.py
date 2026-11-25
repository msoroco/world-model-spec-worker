"""Independent C125751 source-bound comparison audit; legal judgment stays open."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EXPECTED = {'active_vs_off_signal_applicability',
            'opposite_direction_left_turn_exclusion'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def load_case(entry, root):
    case_id = entry['case_id']
    construction = root / entry['construction']
    require(sha(construction) == entry['construction_sha256'], 'Construction changed: ' + case_id)
    bundle = json.loads(construction.read_text())
    config = json.loads(next(x['content'] for x in bundle['files'] if x['path'] == 'config.json'))
    require(config['selected_case_id'] == case_id, 'Selected config differs: ' + case_id)
    spec = entry['compatibility']
    receipt_path = root / spec['receipt']
    require(sha(receipt_path) == spec['sha256'], 'Compatibility receipt changed: ' + case_id)
    receipt = json.loads(receipt_path.read_text())
    require(receipt.get('passed') is True and receipt.get('case_id') == case_id and
            receipt.get('candidate_id') == 'primary' and
            receipt.get('construction_sha256') == entry['construction_sha256'] and
            receipt.get('negative_removed') == 'crossing_history.jsonl',
            'Positive and missing-source proof differs: ' + case_id)
    measurements = receipt.get('measurement_examples', {})
    require({'crossing_identity', 'entry_order', 'device_context',
             'opposite_turn_context'} <= set(measurements),
            'Selected source measurements missing: ' + case_id)
    saved_spec = entry['saved_processing_diagnostic']
    saved_path = root / saved_spec['receipt']
    require(sha(saved_path) == saved_spec['sha256'], 'Saved receipt changed: ' + case_id)
    saved = json.loads(saved_path.read_text())
    require(saved.get('passed') is True and saved.get('recorded_only') is True and
            saved.get('originals_preserved') is True and saved.get('case_id') == case_id and
            saved.get('native_revision', {}).get('construction_sha256') == entry['construction_sha256'],
            'Recorded-only original source proof missing: ' + case_id)
    return {'config': config, 'measured': measurements, 'receipt': receipt,
            'construction_sha256': entry['construction_sha256'],
            'compatibility_sha256': spec['sha256'], 'saved_sha256': saved_spec['sha256']}


def audit_pair(comparison_id, left, right):
    a, b = left['config'], right['config']
    av, bv = left['measured'], right['measured']
    ac, bc = av['crossing_identity']['value'], bv['crossing_identity']['value']
    ae, be = av['entry_order']['value'], bv['entry_order']['value']
    ad, bd = av['device_context']['value'], bv['device_context']['value']
    require(ac['intersection_id'] == bc['intersection_id'] and
            ac['native_map_id'] == bc['native_map_id'] and
            a['site']['crossing_polygon_xy_m'] == b['site']['crossing_polygon_xy_m'] and
            a['actor'] == b['actor'] == 'motor_vehicle_driver' and
            a['rate_hz'] == b['rate_hz'] == 20 and
            a['duration_s'] == b['duration_s'] == 45 and
            ad['native_signal_id'] == bd['native_signal_id'],
            comparison_id + ': fixed site, actor, capture or device differs')
    if comparison_id == 'active_vs_off_signal_applicability':
        require(a['site']['routes'] == b['site']['routes'] and
                a['site']['entrance_road_lanes'] == b['site']['entrance_road_lanes'] and
                a['site']['cameras'] == b['site']['cameras'] and
                ae == be and ae['other_before_ego'] is True and
                ad['observed_signal_states'] == ['Green'] * 3 and
                bd['observed_signal_states'] == ['Off'] * 3 and
                av['entry_order']['sources']['video_frames.jsonl'] ==
                bv['entry_order']['sources']['video_frames.jsonl'],
                'Signal-state difference or fixed trajectories not demonstrated')
    elif comparison_id == 'opposite_direction_left_turn_exclusion':
        turn = bv['opposite_turn_context']['value']['opposite_left_turn_observations']
        require(ac['highway_ids'][0] != ac['highway_ids'][1] and
                bc['highway_ids'][0] == bc['highway_ids'][1] and
                a['site']['cameras'] == b['site']['cameras'] and
                ae == be and ad['observed_signal_states'] ==
                bd['observed_signal_states'] == ['Off'] * 3 and
                b['other_approach_side'] == 'opposite' and
                turn['left_turn_intent_in_original_rows'] is True and
                turn['statutory_exception_judgment'] == 'unresolved' and
                turn['original_body_motion']['other']['projection_on_approach_direction_m'] > 0 and
                len(turn['other_heading_samples_deg']) >= 3,
                'Opposed approach and source-observed left turn not demonstrated')
    else:
        raise ValueError('Unknown comparison: ' + comparison_id)
    return {'comparison_id': comparison_id, 'passed': True,
            'legal_judgment': 'unresolved'}


def audit(root=ROOT, plan=None, manifest=None):
    root = Path(root)
    plan = plan or json.loads((root / 'case-plan.json').read_text())
    manifest = manifest or json.loads((root / 'execution-manifest.json').read_text())
    comparisons = plan['comparisons']
    require(len(comparisons) == 2 and
            {x['comparison_id'] for x in comparisons} == EXPECTED,
            'Exact two-comparison inventory differs')
    entries = {x['case_id']: x for x in manifest['cases']}
    require(len(entries) == 3, 'Exact three-case inventory differs')
    cases = {case_id: load_case(entry, root) for case_id, entry in entries.items()}
    results = []
    for comparison in comparisons:
        ids = comparison['case_ids']
        require(len(ids) == 2 and ids[0] != ids[1] and all(x in cases for x in ids) and
                comparison['fixed_conditions'] and comparison['deliberate_differences'],
                'Comparison declaration incomplete')
        results.append(audit_pair(comparison['comparison_id'], cases[ids[0]], cases[ids[1]]))
    return {'format': 'worker-c125751-comparison-audit', 'passed': True,
            'cases': {k: {field: v[field] for field in
                          ('construction_sha256', 'compatibility_sha256', 'saved_sha256')}
                      for k, v in cases.items()},
            'comparisons': results, 'physical_acceptance_claimed': False,
            'legal_acceptance_claimed': False}


if __name__ == '__main__':
    print(json.dumps(audit(), indent=2))
