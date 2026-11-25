"""Exercise 900 original-frame combination joins on a diagnostic source copy."""
import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
REPO = PACKAGE.parents[1]
sys.path.insert(0, str(PACKAGE))
from caravan_combination import analyze


def main():
    source = REPO / '.runtime-work/c160013-wide-compat-v11'
    if not (source / 'caravan_history.jsonl').is_file():
        raise ValueError('Retained 900-frame diagnostic source required')
    with tempfile.TemporaryDirectory(prefix='c160013-combination-', dir=REPO / '.runtime-work') as temp:
        root = Path(temp)
        for name in ('road_context.json', 'video_frames.jsonl'):
            shutil.copyfile(source / name, root / name)
        relationship = {'drawing_actor_id': 1, 'drawn_actor_id': 8,
                        'drawn_unit_has_motive_power': False}
        data = (json.dumps(relationship, sort_keys=True) + '\n').encode()
        (root / 'towing-source.json').write_bytes(data)
        context = json.loads((root / 'road_context.json').read_text())
        context['towing_relationship_source'] = {
            'path': 'towing-source.json', 'sha256': hashlib.sha256(data).hexdigest(),
            'review_status': 'reviewed_native_relationship'}
        (root / 'road_context.json').write_text(json.dumps(context) + '\n')
        rows = []
        for line in (source / 'caravan_history.jsonl').read_text().splitlines():
            row = json.loads(line)
            powered = next(member for member in row['caravan_members'] if member['actor_id'] == 1)
            drawn = [[x - 4, y] for x, y in powered['body_vertices_xy_m']]
            row['drawn_units'] = [{'actor_id': 8, 'blueprint_id': 'static.prop.diagnostic_trailer',
                                   'body_vertices_xy_m': drawn}]
            row['towing_relationship'] = {'drawing_actor_id': 1, 'drawn_actor_id': 8}
            rows.append(row)
        history = root / 'caravan_history.jsonl'
        history.write_text(''.join(json.dumps(row, separators=(',', ':')) + '\n' for row in rows))
        positive = analyze(root, drawing_actor_id=1, drawn_actor_id=8)
        assert len(positive['samples']) == 900
        assert all(sample['following_actor_id'] == 2 and sample['following_gap_opening_m'] > 0
                   for sample in positive['samples'])
        (root / 'towing-source.json').write_text('changed\n')
        try:
            analyze(root, drawing_actor_id=1, drawn_actor_id=8)
        except ValueError as error:
            assert 'Changed original towing relationship source' in str(error)
        else:
            raise AssertionError('Changed source accepted')
        (root / 'towing-source.json').write_bytes(data)
        rows[1]['towing_relationship']['drawn_actor_id'] = 99
        history.write_text(''.join(json.dumps(row, separators=(',', ':')) + '\n' for row in rows))
        try:
            analyze(root, drawing_actor_id=1, drawn_actor_id=8)
        except ValueError as error:
            assert 'per-frame towing relationship mismatch' in str(error)
        else:
            raise AssertionError('Changed original frame relationship accepted')
        print(json.dumps({'format': 'worker-combination-diagnostic-proof',
                          'frames_checked': 900, 'positive_passed': True,
                          'changed_relationship_source_rejected': True,
                          'changed_frame_link_rejected': True,
                          'source_sha256': positive['original_source_sha256'],
                          'physical_acceptance_claimed': False,
                          'without_danger_judgment': 'unresolved'}, sort_keys=True))


if __name__ == '__main__':
    main()
