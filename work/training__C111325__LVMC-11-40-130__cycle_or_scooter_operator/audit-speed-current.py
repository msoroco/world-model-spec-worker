"""Independent source and construction audit for the bicycle-speed draft pair."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
FROZEN = ROOT / 'inputs' / HERE.name / 'assignment.json'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    frozen = json.loads(FROZEN.read_text())
    plan = json.loads((HERE / 'case-plan.json').read_text())
    proof = json.loads((HERE / 'speed-source-proof.json').read_text())
    manifest = json.loads((HERE / 'native/draft-execution-manifest.json').read_text())
    context = json.loads((HERE / 'diagnostic-speed/context.json').read_text())
    if (frozen['law']['text'] != plan['source_law']['text'] or
            frozen['cell']['cell_id'] != 'C111325' or
            frozen['actor'] != 'cycle_or_scooter_operator' or
            len(plan['cases']) != 2 or len(manifest['cases']) != 2 or
            len(proof['records']) != 2 or not proof['passed']):
        raise ValueError('Frozen speed scope or pair incomplete')
    if (context['control'] != 'stop_sign' or context['actor_requested'] != 'bicycle' or
            context['physical_conditions_verified'] or manifest['delivery_ready']):
        raise ValueError('Context or authority overstated')
    summaries = []
    for index, condition in enumerate(('condition_a', 'condition_b')):
        path = HERE / 'diagnostic-speed' / (condition + '.jsonl')
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        if len(rows) != 600:
            raise ValueError('Source duration changed')
        if (manifest['cases'][index]['case_id'] != plan['cases'][index]['case_id'] or
                sha(HERE / 'native' / manifest['cases'][index]['construction']) !=
                manifest['cases'][index]['construction_sha256'] or
                proof['records'][index]['source_sha256'] != sha(path)):
            raise ValueError('Exact source or construction binding changed')
        speeds = []
        for frame, row in enumerate(rows):
            if (row['frame'] != frame or row['time_s'] != frame / 20 or
                    row['requested_speed_condition'] != condition or
                    row['stop_line_x_m'] != 0.0 or
                    row['context_id'] != context['context_id'] or
                    row['original_native_observed'] or row['legal_verdict'] is not None):
                raise ValueError('Frame or condition changed')
            if frame:
                speed = (row['bicycle_center_xy_m'][0] - rows[frame-1]['bicycle_center_xy_m'][0]) * 20
                if speed < 0 or speed > 5.01:
                    raise ValueError('Impossible bicycle motion in draft')
                speeds.append(speed)
        first_stop = next(i for i, row in enumerate(rows) if row['bicycle_center_xy_m'][0] == -2.0)
        if (rows[0]['bicycle_center_xy_m'] != [-50.0, -1.75] or
                rows[-1]['bicycle_center_xy_m'] != [-2.0, -1.75] or
                proof['records'][index]['first_stopped_frame'] != first_stop or
                abs(proof['records'][index]['peak_position_derived_speed_mps'] - max(speeds)) > 1e-6):
            raise ValueError('Position-derived speed or stop disagrees')
        summaries.append({'condition': condition, 'first_stopped_frame': first_stop,
                          'peak_position_derived_speed_mps': round(max(speeds), 6),
                          'source_sha256': sha(path)})
    if not (summaries[0]['peak_position_derived_speed_mps'] <
            summaries[1]['peak_position_derived_speed_mps'] and
            summaries[1]['first_stopped_frame'] < summaries[0]['first_stopped_frame']):
        raise ValueError('Controlled speed contrast absent')
    result = {'format': 'c111325-independent-source-audit-v1', 'passed': True,
              'frozen_assignment_sha256': sha(FROZEN),
              'draft_manifest_sha256': sha(HERE / 'native/draft-execution-manifest.json'),
              'source_proof_sha256': sha(HERE / 'speed-source-proof.json'),
              'context_sha256': sha(HERE / 'diagnostic-speed/context.json'),
              'condition_summaries': summaries,
              'fixed_conditions': ['cell', 'stop_sign', 'bicycle_requested',
                                   'visibility', 'wet_road', 'pedestrian_presence',
                                   'route_start', 'stop_line', 'stop_position'],
              'controlled_variable': 'bicycle_approach_speed',
              'original_native_observed': False,
              'prudence_verdict_claimed': False}
    target = HERE / 'speed-independent-audit.json'
    target.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'passed': True, 'audit_sha256': sha(target), 'summaries': summaries}))


if __name__ == '__main__':
    main()
