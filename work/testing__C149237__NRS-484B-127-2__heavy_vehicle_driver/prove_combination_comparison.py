"""Exercise the independent combination comparison and source/fixed-condition rejects."""
import hashlib
import json
import shutil
import tempfile
from pathlib import Path

from combination_comparison_audit import audit

ROOT = Path(__file__).resolve().parents[2]
SINGLE = ROOT/'.runtime-work/c149237-gap_at_500ft-saved-v16/v0001/analysis'
COMBINATION = ROOT/'.runtime-work/c149237-combination-selected/saved-v3/v0001/analysis'
FILES = ('config.json', 'result.json', 'analysis-report.json', 'road_context.json',
         'truck_history.jsonl', 'video_frames.jsonl')


def paths(combination=COMBINATION):
    return {'gap_at_500ft':SINGLE, 'combination_at_500ft':combination}


def reject(modified, expected):
    try:
        audit(paths(modified))
    except (ValueError, FileNotFoundError) as error:
        if expected not in str(error):
            raise
    else:
        raise AssertionError('Changed combination comparison source was accepted: '+expected)


def main():
    positive = audit(paths())
    with tempfile.TemporaryDirectory(prefix='c149237-combination-comparison-',
                                     dir=ROOT/'.runtime-work') as temporary:
        source = Path(temporary)
        for name in FILES:
            shutil.copyfile(COMBINATION/name, source/name)
        original = [json.loads(line) for line in (source/'truck_history.jsonl').read_text().splitlines()]
        def write_rows(rows):
            (source/'truck_history.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows))
            report = json.loads((source/'analysis-report.json').read_text())
            report['measurements']['minimum_sampled_body_gap_m']['sources']['truck_history.jsonl'] = hashlib.sha256(
                (source/'truck_history.jsonl').read_bytes()).hexdigest()
            (source/'analysis-report.json').write_text(json.dumps(report)+'\n')
        rows = json.loads(json.dumps(original))
        rows[0]['ego']['velocity_mps'] = [10, 0, 0]
        write_rows(rows)
        reject(source, 'Combined tractor identity or velocity differs from component')
        rows[0]['ego']['components']['tractor']['velocity_mps'] = [10, 0, 0]
        write_rows(rows)
        reject(source, 'Fixed combination comparison condition differs: velocities')
        rows = json.loads(json.dumps(original))
        rows[0]['ego']['components']['trailer']['lane_id'] = 2
        write_rows(rows)
        reject(source, 'Combination component changed sourced road or lane')
        rows = json.loads(json.dumps(original))
        trailer = rows[0]['ego']['components']['trailer']['body_vertices_xy_m']
        rows[0]['ego']['components']['trailer']['body_vertices_xy_m'] = [[x-10, y] for x, y in trailer]
        rows[0]['ego']['body_vertices_xy_m'] = (rows[0]['ego']['components']['tractor']['body_vertices_xy_m'] +
                                                 rows[0]['ego']['components']['trailer']['body_vertices_xy_m'])
        write_rows(rows)
        reject(source, 'Combination component hitch geometry differs')
        rows = json.loads(json.dumps(original))
        rows[0]['ego']['components'].pop('trailer')
        write_rows(rows)
        reject(source, 'Missing original combination components')
        (source/'truck_history.jsonl').unlink()
        reject(source, 'truck_history.jsonl')
    print(json.dumps({'positive':positive, 'negative_forged_merged_velocity':'rejected',
                      'negative_changed_component_lane':'rejected',
                      'negative_changed_hitch_geometry':'rejected',
                      'negative_changed_fixed_speed':'rejected',
                      'negative_missing_trailer':'rejected',
                      'negative_missing_original_history':'rejected'}, indent=2))


if __name__ == '__main__':
    main()
