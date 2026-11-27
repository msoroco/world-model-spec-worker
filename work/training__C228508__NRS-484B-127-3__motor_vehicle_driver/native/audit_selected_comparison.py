"""Independent raw-body comparison of two selected caravan diagnostic probes."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def extent(body):
    if len(body) != 4:
        raise ValueError('Original body extent incomplete')
    return min(vertex[0] for vertex in body), max(vertex[0] for vertex in body)


def audit(suffix):
    base = ROOT / 'compat-source' / suffix
    samples = rows(base / 'native_samples.jsonl')
    mapping = rows(base / 'video_frames.jsonl')
    if len(samples) != len(mapping) or len(samples) != 600:
        raise ValueError('Original duration/frame join differs')
    clearance = []
    velocities = set()
    for index, (sample, frame) in enumerate(zip(samples, mapping)):
        if sample['native_frame'] != frame['carla_frame'] or frame['video_frame'] != index:
            raise ValueError('Original frame identity differs')
        if abs(sample['time_s'] - frame['time_s']) > 1e-9:
            raise ValueError('Original timestamp differs')
        actors = sample['actors']
        if set(actors) != {'lead', 'ego_combination', 'trailer_proxy',
                           'rear', 'potential_entrant'}:
            raise ValueError('Original five-body inventory differs')
        for actor in actors.values():
            velocities.add(tuple(actor['native_velocity_xy_mps']))
        lead = extent(actors['lead']['native_body_xy_m'])
        tractor = extent(actors['ego_combination']['native_body_xy_m'])
        trailer = extent(actors['trailer_proxy']['native_body_xy_m'])
        rear = extent(actors['rear']['native_body_xy_m'])
        combination = (min(tractor[0], trailer[0]), max(tractor[1], trailer[1]))
        clearance.append((lead[0] - combination[1], combination[0] - rear[1]))
    lead_min = min(pair[0] for pair in clearance)
    rear_min = min(pair[1] for pair in clearance)
    selected = ROOT / 'selected' / ('' if suffix == 'probe_a' else suffix) / 'primary'
    receipt = json.loads((selected /
                          'compatibility/compatibility.json').read_text())
    value = receipt['measurement_examples']['caravan_space_measurement']['value']
    measured = value['minimum_clear_space_m']
    if measured != {'lead_to_combination_m':lead_min,
                    'combination_to_rear_m':rear_min}:
        raise ValueError('Selected meter differs from independent raw-body audit')
    if value['legal_sufficiency_judgment'] is not None or not value['trailer_coupling_unverified']:
        raise ValueError('Diagnostic result overclaims legal or coupled-tow evidence')
    return {'case_id':receipt['case_id'], 'frames':len(samples),
            'minimum_clear_space_m':measured,
            'velocity_vectors_mps':[list(v) for v in sorted(velocities)],
            'source_sha256':{name:sha(base / name) for name in
                             ('native_samples.jsonl','video_frames.jsonl')},
            'compatibility_receipt_sha256':sha(selected /
                                              'compatibility/compatibility.json'),
            'synthetic_diagnostic':True,
            'original_native_or_legal_verdict_claimed':False}


def main():
    a, b = audit('probe_a'), audit('probe_b')
    gaps = (a['minimum_clear_space_m'], b['minimum_clear_space_m'])
    if gaps != ({'lead_to_combination_m':30.0,'combination_to_rear_m':30.0},
                {'lead_to_combination_m':8.0,'combination_to_rear_m':8.0}):
        raise ValueError('Selected deliberate gap comparison differs')
    if a['velocity_vectors_mps'] != b['velocity_vectors_mps']:
        raise ValueError('Comparison altered realized diagnostic velocity')
    report = {'format':'c228508-independent-selected-comparison-v1',
              'cases':[a,b],'deliberate_difference':'caravan_entry_gap',
              'clearance_difference_m':22.0,
              'fixed_conditions':['same authored highway, actor inventory, 600-frame duration',
                                  'same 6 m/s synthetic realized motion and four camera profile'],
              'legal_sufficiency_inferred':False,
              'physical_or_coupling_acceptance_claimed':False}
    target = ROOT / 'selected-comparison-audit.json'
    target.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'passed':True,'report_sha256':sha(target),
                      'clearance_difference_m':22.0,'synthetic_diagnostic':True}))


if __name__ == '__main__':
    main()
