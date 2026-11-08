"""Independent saved-row replay of both response metrics and retained controls."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from measure_response import measure_response

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit():
    proof_path = HERE/'response-proof.json'
    proof = json.loads(proof_path.read_text())
    if (proof['format'] != 'c102951-saved-response-proof-v1' or
            proof['processor_sha256'] != sha(HERE/'measure_response.py') or
            proof['pass_processor_sha256'] != sha(HERE/'measure_pass.py') or
            proof['original_native_observed'] or proof['delivery_ready'] or
            len(proof['fixtures']) != 4 or len(proof['negative_controls']) != 4 or
            not all(case['rejected'] is True for case in proof['negative_controls'])):
        raise ValueError('Response proof provenance, status or coverage differs')
    measured = []
    for fixture in proof['fixtures']:
        distance = fixture['distance_m']
        variant = fixture['variant']
        folder = (HERE/'response-fixtures'/'reaction-170' if variant == 'two_vehicle_slowdown'
                  else HERE/'saved-fixtures'/str(distance))
        hashes = {name: sha(folder/name) for name in ('native-observed.jsonl', 'road-readback.json')}
        if hashes != fixture['source_hashes'] or hashes != fixture['measurement']['source_hashes']:
            raise ValueError('Response source hash differs')
        rows = [json.loads(line) for line in (folder/'native-observed.jsonl').read_text().splitlines()]
        if len(rows) != 480 or any(row['frame'] != i or abs(row['time_s']-(i+1)/20) > 1e-6
                                   for i, row in enumerate(rows)):
            raise ValueError('Response row frame or time differs')
        start = fixture['measurement']['pass_entry_frame']
        finish = fixture['measurement']['pass_return_frame']
        if not (20 <= start < finish < 475):
            raise ValueError('Response pass window differs')
        for actor in ('oncoming', 'overtaken'):
            speeds = [row[actor+'_speed_mps'] for row in rows]
            if any(not isinstance(v, (int, float)) or v < 0 for v in speeds):
                raise ValueError('Response speed invalid')
            baseline = sorted(speeds[:20]); baseline = (baseline[9]+baseline[10])/2
            windows = [(i, (speeds[i]-speeds[i-5])/(rows[i]['time_s']-rows[i-5]['time_s']))
                       for i in range(start, finish+1)]
            min_frame, min_accel = min(windows, key=lambda pair: (pair[1], pair[0]))
            hard = [i for i, value in windows if value < -3]
            expected = {'prepass_median_speed_mps': round(baseline, 3),
                        'minimum_left_phase_speed_mps': round(min(speeds[start:finish+1]), 3),
                        'maximum_left_phase_speed_drop_mps': round(max(0, baseline-min(speeds[start:finish+1])), 3),
                        'minimum_five_frame_acceleration_mps2': round(min_accel, 3),
                        'minimum_acceleration_frame': min_frame,
                        'five_frame_hard_deceleration_count': len(hard),
                        'first_five_frame_hard_deceleration_frame': hard[0] if hard else None}
            if fixture['measurement']['response'][actor] != expected:
                raise ValueError('Independent response metric differs')
            if variant == 'two_vehicle_slowdown' and (expected['maximum_left_phase_speed_drop_mps'] != 4 or
                                                       not hard):
                raise ValueError('Synthetic response signal absent')
            if variant == 'two_vehicle_slowdown':
                direction = -1 if actor == 'oncoming' else 1
                positions = [row[actor+'_x_m'] for row in rows]
                if any(abs(positions[i]-positions[i-1]-direction*speeds[i]/20) > 1.1e-4
                       for i in range(1, len(rows))):
                    raise ValueError('Synthetic reaction position and speed differ')
        if any(fixture['measurement'][field] is not None for field in
               ('caused_by_passing_judgment', 'interference_judgment',
                'safe_distance_judgment', 'legal_verdict')) or fixture['measurement']['delivery_ready']:
            raise ValueError('Response measurement claimed a legal conclusion')
        measured.append({'distance_m': distance, 'variant': variant, 'rows': len(rows),
                         'source_hashes': hashes})
    reaction = HERE/'response-fixtures'/'reaction-170'
    controls = []
    for mutation in ('source_hash', 'negative_speed', 'missing_frame', 'altered_time'):
        with tempfile.TemporaryDirectory(dir=HERE) as temporary:
            copy = Path(temporary)/'saved'
            shutil.copytree(reaction, copy)
            rows_path = copy/'native-observed.jsonl'
            if mutation != 'source_hash':
                rows = [json.loads(line) for line in rows_path.read_text().splitlines()]
                if mutation == 'negative_speed': rows[60]['oncoming_speed_mps'] = -1
                elif mutation == 'missing_frame': rows.pop()
                else: rows[60]['time_s'] = 99
                rows_path.write_text(''.join(json.dumps(row, sort_keys=True)+'\n' for row in rows))
            try:
                if mutation == 'source_hash':
                    measure_response(copy, {'native-observed.jsonl': '0'*64,
                                            'road-readback.json': sha(copy/'road-readback.json')})
                else:
                    measure_response(copy)
            except (ValueError, TypeError):
                controls.append(mutation)
            else:
                raise ValueError('Independent negative replay accepted '+mutation)
    receipt = {'format': 'c102951-independent-response-audit-v1',
               'assignment_id': HERE.parent.name, 'proof_sha256': sha(proof_path),
               'fixtures_recomputed': measured, 'saved_rows_recomputed': 1920,
               'negative_controls_replayed': controls, 'original_native_observed': False,
               'delivery_ready': False}
    (HERE/'response-audit.json').write_text(json.dumps(receipt, indent=2)+'\n')
    return receipt


if __name__ == '__main__':
    print(json.dumps(audit()))
