"""Independently measure moving facility occupancy in eight exact v1 packages."""
import hashlib
import json
import math
from pathlib import Path
from audit_geometry import clipped_area

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CANDIDATES = ('primary', 'fallback1', 'fallback2', 'fallback3')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def moving_overlap(row, bounds):
    area = clipped_area(row['native_body_xy_m'], bounds)
    return row['speed_mps'] > .1 and area > .01


def package(suffix, candidate, manifest):
    filename = 'package-compatibility-' + suffix + (
        '' if candidate == 'primary' else '-' + candidate) + '.log'
    lines = (HERE / filename).read_text().splitlines()
    if len(lines) != 2 or not lines[0].startswith('scratch '):
        raise ValueError('Incomplete exact package log: ' + filename)
    scratch = Path(lines[0][8:])
    if ROOT / '.runtime-work' not in scratch.parents:
        raise ValueError('Package fixture is outside ignored scratch')
    output = scratch / 'output'
    receipt = read(output / 'compatibility.json')
    log = json.loads(lines[1])
    case = next(c for c in manifest['cases'] if c['case_id'].endswith('__' + suffix))
    construction = case if candidate == 'primary' else next(
        c for c in case['candidates'] if c['id'] == candidate)
    if (any(receipt.get(key) != value for key, value in log['positive'].items()) or
        not receipt['passed'] or
        receipt['case_id'] != case['case_id'] or
        receipt['candidate_id'] != candidate or
        receipt['construction_sha256'] != construction['construction_sha256'] or
        sha(HERE / construction['construction']) != construction['construction_sha256']):
        raise ValueError('Exact positive construction or receipt differs')
    negative = log['entry_negative']
    if (negative['exit_code'] == 0 or negative['removed'] != 'entry-sources.json' or
        negative['error_contains'] not in (scratch / 'entry-negative-analysis.log').read_text()):
        raise ValueError('Exact missing entry source did not reject')
    source = read(output / 'entry-sources.json')
    if source['source_kind'] != 'synthetic_cpu_fixture' or set(source['sha256']) != {
        'native_samples.jsonl', 'road_geometry.json'}:
        raise ValueError('Moving source provenance differs')
    if any(sha(output / name) != digest for name, digest in source['sha256'].items()):
        raise ValueError('Moving source hash differs')
    motion = rows(output / 'native_samples.jsonl')
    geometry = read(output / 'road_geometry.json')
    result = read(output / 'result.json')
    report = read(output / 'analysis-report.json')
    if (len(motion) != 480 or source['sha256'] !=
        report['measurements']['moving_entry_observation']['sources'] or
        result['accepted'] or result['legal_verdict_claimed'] or
        geometry['native_facility_design_verified'] is not False):
        raise ValueError('Moving source or report scope differs')
    bounds = geometry['bicycle_facility_native_xy_bounds_m']
    flags = []
    for i, row in enumerate(motion):
        if (row['native_frame'] != motion[0]['native_frame'] + i or
            not math.isclose(row['time_s'], (i + 1) / 20, abs_tol=1e-6) or
            row['native_road_id'] != geometry['road_id'] or
            row.get('synthetic_diagnostic') is not True):
            raise ValueError('Original frame, road or provenance differs')
        flags.append(moving_overlap(row, bounds))
    count = sum(flags)
    measured = report['measurements']['moving_entry_observation']['value']
    if (count != (0 if suffix == 'probe_a' else 71) or
        result['measured_values']['moving_occupied_frames'] != count or
        measured['moving_occupied_frames'] != count or
        measured['facility_designation_verified'] is not False or
        measured['exception_a_observed'] != 'unresolved' or
        measured['legal_verdict_claimed'] is not False):
        raise ValueError('Independent moving occupancy differs from saved outputs')
    return motion, geometry, {'candidate': candidate, 'case_suffix': suffix,
        'moving_occupied_frames': count, 'first_occupied_native_frame': next(
            (row['native_frame'] for row, flag in zip(motion, flags) if flag), None),
        'positive_receipt_sha256': sha(output / 'compatibility.json'),
        'missing_source_log_sha256': sha(scratch / 'entry-negative-analysis.log')}


def main():
    manifest = read(HERE / 'draft-execution-manifest.json')
    manifest_sha = sha(HERE / 'draft-execution-manifest.json')
    pairs = []
    for candidate in CANDIDATES:
        outside, outside_geometry, outside_result = package('probe_a', candidate, manifest)
        inside, inside_geometry, inside_result = package('probe_b', candidate, manifest)
        if outside_geometry != inside_geometry:
            raise ValueError('Facility geometry differs across controlled pair')
        speed_different = 0
        for left, right in zip(outside, inside):
            for key in ('native_frame', 'time_s', 'native_road_id'):
                if left[key] != right[key]:
                    raise ValueError('Controlled moving schedule differs: ' + key)
            if left['native_center_xy_m'][0] != right['native_center_xy_m'][0]:
                raise ValueError('Controlled longitudinal route differs')
            if (left['speed_mps'] > .1) != (right['speed_mps'] > .1):
                raise ValueError('Moving/stopped state differs')
            speed_different += left['speed_mps'] != right['speed_mps']
        if outside_result['moving_occupied_frames'] != 0 or inside_result['moving_occupied_frames'] != 71:
            raise ValueError('Controlled moving occupancy polarity differs')
        pairs.append({'candidate': candidate, 'reference': outside_result,
                      'contrast': inside_result,
                      'speed_magnitude_different_frames': speed_different})
    proof = {'format': 'c10052-drive-within-independent-cpu-v1',
             'passed': True, 'source_kind': 'synthetic_cpu_fixture',
             'manifest_sha256': manifest_sha,
             'candidate_pairs': pairs, 'selected': False,
             'facility_designation_verified': False,
             'statutory_exception_resolved': False,
             'physical_or_legal_verdict_claimed': False}
    if sha(HERE / 'draft-execution-manifest.json') != manifest_sha:
        raise ValueError('Manifest changed during audit')
    (HERE / 'drive-within-cpu-proof.json').write_text(json.dumps(proof, indent=2) + '\n')
    return proof


if __name__ == '__main__':
    print(json.dumps(main(), sort_keys=True))
