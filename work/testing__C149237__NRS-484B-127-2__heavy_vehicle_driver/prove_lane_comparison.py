"""Exercise source-bound lane comparison and two negative controls."""
import hashlib
import json
import shutil
import tempfile
from pathlib import Path

from lane_comparison_audit import CASES, audit

ROOT = Path(__file__).resolve().parents[2]
PATHS = {s: ROOT/'.runtime-work'/('c149237-'+s+('-saved-v17' if s=='gap_below_500ft' else '-saved-v16'))/'v0001/analysis' for s in CASES}
FILES = ('config.json', 'result.json', 'analysis-report.json', 'road_context.json',
         'truck_history.jsonl', 'video_frames.jsonl')


def main():
    positive = audit(PATHS)
    with tempfile.TemporaryDirectory(dir=ROOT/'.runtime-work', prefix='c149237-lane-audit-') as tmp:
        changed = Path(tmp)/'changed'
        changed.mkdir()
        for name in FILES:
            shutil.copyfile(PATHS['two_same_direction_lanes']/name, changed/name)
        road = json.loads((changed/'road_context.json').read_text())
        road['same_direction_lane_count'] = 1
        (changed/'road_context.json').write_text(json.dumps(road)+'\n')
        report = json.loads((changed/'analysis-report.json').read_text())
        checksum = hashlib.sha256((changed/'road_context.json').read_bytes()).hexdigest()
        report['measurements']['minimum_sampled_body_gap_m']['sources']['road_context.json'] = checksum
        (changed/'analysis-report.json').write_text(json.dumps(report)+'\n')
        negative = dict(PATHS, two_same_direction_lanes=changed)
        try:
            audit(negative)
        except ValueError as error:
            if 'source lane count differs' not in str(error):
                raise
        else:
            raise AssertionError('Changed lane count was accepted')
        (changed/'truck_history.jsonl').unlink()
        try:
            audit(negative)
        except FileNotFoundError:
            pass
        else:
            raise AssertionError('Missing truck history was accepted')
    print(json.dumps({'positive': positive, 'changed_lane_count': 'rejected',
                      'missing_original_history': 'rejected'}, indent=2))


if __name__ == '__main__':
    main()
