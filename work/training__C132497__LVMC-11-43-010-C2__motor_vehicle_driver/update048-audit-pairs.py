"""Independently audit migrated-input right-lane versus adjacent-lane CPU pairs."""
import copy
import hashlib
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
CANDIDATES = ('primary', 'fallback1', 'fallback2', 'fallback3')
FIXED = ('assignment_id', 'assignment_sha256', 'law_id', 'cell_id', 'actor',
         'rate_hz', 'frames', 'road_sha256', 'camera_policy', 'requested_speed_mps',
         'pre_entry_dwell_s', 'circulation_direction')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def require(value, message):
    if not value:
        raise ValueError(message)


def side(case, candidate):
    manifest = read(HERE / 'update048-execution-manifest.json')
    entry = next(e for e in manifest['cases'] if e['case_id'].endswith('__' + case))
    selected = entry if candidate == 'primary' else next(x for x in entry['candidates'] if x['id'] == candidate)
    construction_path = HERE / selected['construction']
    require(sha(construction_path) == selected['construction_sha256'], 'Selected construction changed')
    construction = read(construction_path)
    config = json.loads(next(f['content'] for f in construction['files'] if f['path'] == 'config.json'))
    proof = HERE / 'update048-proof' / case / candidate
    processing = read(proof / 'processing.json')
    require(processing['passed'] and processing['originals_preserved'] and
            processing['native_revision']['construction_sha256'] == selected['construction_sha256'] and
            processing['candidate_id'] == candidate and processing['case_id'] == entry['case_id'] and
            not processing['physical_acceptance_claimed'], 'Selected saved receipt changed')
    saved = Path(processing['result'])
    require(saved.is_file(), 'Selected saved result missing')
    target = proof / 'saved-result.json'
    shutil.copyfile(saved, target)
    require(sha(target) == processing['result_sha256'], 'Saved result SHA differs')
    result = read(target)
    require(result['case_id'] == entry['case_id'] and result['provenance_kind'] == 'synthetic_local_diagnostic'
            and result['accepted'] is False and result['maneuver_completed'] is False,
            'Diagnostic result overclaims original physical completion')
    return config, result, {'construction_sha256': selected['construction_sha256'],
                            'processing_sha256': sha(proof / 'processing.json'),
                            'result_sha256': sha(target)}


def compare(left, right, left_result, right_result):
    for key in FIXED:
        require(left.get(key) == right.get(key), 'Fixed condition changed: ' + key)
    require(left['requested_lane_id'] == -2 and right['requested_lane_id'] == -1,
            'Declared governed lane contrast differs')
    require(left_result['measured_values']['right_lane_exit'] is True and
            right_result['measured_values']['right_lane_exit'] is False,
            'Source-derived saved lane contrast differs')
    require(left_result['realized_observables']['right_lane_frames']['value'] > 0 and
            right_result['realized_observables']['right_lane_frames']['value'] == 0,
            'Source-derived circulation lane frames differ')
    return True


def main():
    pairs = []
    for candidate in CANDIDATES:
        a, ra, ah = side('reference', candidate)
        b, rb, bh = side('contrast', candidate)
        compare(a, b, ra, rb)
        pairs.append({'candidate': candidate, 'reference': ah, 'contrast': bh,
                      'requested_lane_ids': [-2, -1],
                      'measured_right_lane_frames': [ra['realized_observables']['right_lane_frames']['value'],
                                                     rb['realized_observables']['right_lane_frames']['value']],
                      'passed': True})
    a, ra, _ = side('reference', 'primary')
    b, rb, _ = side('contrast', 'primary')
    negatives = {}
    changed = copy.deepcopy(b)
    changed['requested_speed_mps'] += 1
    try:
        compare(a, changed, ra, rb)
    except ValueError as error:
        negatives['changed_fixed_speed'] = str(error)
    changed = copy.deepcopy(rb)
    changed['measured_values']['right_lane_exit'] = True
    try:
        compare(a, b, ra, changed)
    except ValueError as error:
        negatives['collapsed_observed_contrast'] = str(error)
    if len(negatives) != 2:
        raise ValueError('Independent pair negative controls failed')
    output = HERE / 'update048-pair-audit.json'
    output.write_text(json.dumps({'format': 'c132497-current-input-pair-audit-v1',
                                  'assignment_id': HERE.name, 'pair_count': len(pairs),
                                  'passed': len(pairs) == 4, 'pairs': pairs,
                                  'negative_rejections': negatives,
                                  'original_native_observed': False, 'accepted': False}, indent=2) + '\n')
    print(json.dumps({'pair_count': len(pairs), 'sha256': sha(output)}))


if __name__ == '__main__':
    main()
