"""Independent source/geometry audit of all heavy-vehicle saved CPU fixtures."""
import hashlib
import json
from pathlib import Path

from measure_saved import measure

HERE = Path(__file__).resolve().parent
CASES = ('reference','contrast')
CANDIDATES = ('primary','fallback1','fallback2','fallback3')
FILES = ('native-observed.jsonl','native-map-readback.json','video_frames.jsonl',
         'capture/evidence.jsonl','native-capture-report.json')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def lines(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def audit():
    proof_path = HERE/'saved-proof.json'
    proof = json.loads(proof_path.read_text())
    if (proof['format'] != 'c422978-heavy-saved-cpu-proof-v1' or
            proof['processor_sha256'] != sha(HERE/'measure_saved.py') or
            proof['original_native_observed'] or proof['delivery_ready'] or
            len(proof['positives']) != 8 or len(proof['negatives']) != 40):
        raise ValueError('Saved CPU proof identity or scope differs')
    seen, measured_rows = set(), 0
    for positive in proof['positives']:
        case, candidate = positive['case'], positive['candidate']
        if case not in CASES or candidate not in CANDIDATES or (case,candidate) in seen:
            raise ValueError('Saved CPU candidate identity differs')
        seen.add((case,candidate))
        folder = HERE/'saved-fixtures'/case/candidate
        requested = lines(HERE/'drafts'/case/candidate/'requested-tracks.jsonl')
        actor = lines(folder/'native-observed.jsonl')
        video = lines(folder/'video_frames.jsonl')
        capture = lines(folder/'capture/evidence.jsonl')
        survey = json.loads((folder/'native-map-readback.json').read_text())
        report = json.loads((folder/'native-capture-report.json').read_text())
        if any(len(rows) != 480 for rows in (requested,actor,video,capture)):
            raise ValueError('Saved fixture frame count differs')
        if (survey['observed_body_width_m'] != 2.4 or
                survey['city_location_verified'] or report['accepted'] or
                report['bundle_config_sha256'] != sha(HERE/'drafts'/case/candidate/'config.json')):
            raise ValueError('Saved fixture source declaration differs')
        overlap, inside, lane_frames = [], [], 0
        for i, (target, row, image, evidence) in enumerate(zip(requested,actor,video,capture)):
            x, authored_y = target['requested_center_xy_m']
            y = -authored_y
            if (row['frame'] != i or row['native_frame'] != 1000+i or
                    abs(row['time_s']-(.05+i/20)) > 1e-4 or
                    row['source_kind'] != 'synthetic_cpu' or
                    row['vehicle_blueprint'] != 'vehicle.carlamotors.carlacola' or
                    row['center_native_xy_m'] != [x,y] or
                    row['speed_mps'] != 4 or
                    image['video_frame'] != i or image['native_frame'] != 1000+i or
                    image['carla_frame'] != 1000+i or
                    evidence['original_frame'] != 1000+i):
                raise ValueError('Saved row identity or requested placement differs')
            body = row['body_native_xy_m']
            expected = [[round(x-4,4),round(y-1.2,4)],
                        [round(x-4,4),round(y+1.2,4)],
                        [round(x+4,4),round(y-1.2,4)],
                        [round(x+4,4),round(y+1.2,4)]]
            if body != expected:
                raise ValueError('Saved body differs from authored synthetic geometry')
            if x+4 > 0 and x-4 < 140 and y+1.2 > 3.5 and y-1.2 < 7.5:
                overlap.append(i)
            if x-4 >= 0 and x+4 <= 140 and y-1.2 >= 3.5 and y+1.2 <= 7.5:
                inside.append(i)
            if row['native_lane_id'] == -2:
                lane_frames += 1
            measured_rows += 1
        measurement = positive['measurement']
        expected_hashes = {name:sha(folder/name) for name in FILES}
        if (measurement['source_hashes'] != expected_hashes or
                measurement['moving_sidewalk_overlap_frames'] != len(overlap) or
                measurement['first_moving_sidewalk_overlap_frame'] != (overlap[0] if overlap else None) or
                measurement['full_body_inside_sidewalk_frames'] != len(inside) or
                measurement['native_sidewalk_lane_readback_frames'] != lane_frames or
                measurement['legal_verdict'] is not None or
                measure(folder,expected_hashes) != measurement):
            raise ValueError('Saved independent measurement differs')
    if seen != {(case,candidate) for case in CASES for candidate in CANDIDATES}:
        raise ValueError('Saved candidate coverage incomplete')
    mutation_set = {'body_center','source_hash','video_join','capture_join','width_readback'}
    if {(n['case'],n['candidate'],n['mutation']) for n in proof['negatives']} != {
            (case,candidate,mutation) for case,candidate in seen for mutation in mutation_set} or \
            not all(n['rejected'] is True for n in proof['negatives']):
        raise ValueError('Saved negative coverage differs')
    result = {'format':'c422978-heavy-independent-saved-audit-v1',
              'proof_sha256':sha(proof_path), 'exact_positive_cases':len(seen),
              'source_rows_recomputed':measured_rows,
              'semantic_and_hash_negatives':len(proof['negatives']),
              'original_native_observed':False,'delivery_ready':False}
    (HERE/'saved-audit.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__ == '__main__':
    result = audit()
    print(json.dumps({'positives':result['exact_positive_cases'],
                      'rows':result['source_rows_recomputed'],
                      'negatives':result['semantic_and_hash_negatives']}))
