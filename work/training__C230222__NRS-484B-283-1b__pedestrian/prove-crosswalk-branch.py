"""Construct two same-cell synthetic crossing-location probes on an authored Native road."""
import json
from pathlib import Path
import shutil
import sys
import tempfile
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE / 'native'))
from crosswalk_branch import marking, measure, sha


def write_rows(path, rows):
    path.write_text(''.join(json.dumps(row, allow_nan=False) + '\n' for row in rows))


def write_context(folder, rows):
    context = {'source_kind': 'synthetic_scene_request',
               'frozen_cell': {'layout': 'road', 'maneuver': 'travel', 'control': 'curb'},
               'road_sha256': sha(folder / 'road-crosswalk.xodr'),
               'curb_samples_sha256': sha(folder / 'curb-samples.jsonl'),
               'pedestrian_id': rows[0]['pedestrian_id'],
               'vehicle_id': rows[0]['vehicle_id'],
               'marked_crosswalk_pixel_status': 'unobserved',
               'designated_place_prohibition': 'unreviewed'}
    (folder / 'crosswalk-context.json').write_text(json.dumps(context, indent=2) + '\n')


def main():
    source = json.loads((HERE / 'curb-summary.json').read_text())['records'][0]
    original = Path(source['retained_positive']) / 'curb-samples.jsonl'
    rows = [json.loads(line) for line in original.read_text().splitlines() if line.strip()]
    root = Path(tempfile.mkdtemp(dir=ROOT / '.runtime-work', prefix='c230222-crosswalk-'))
    records = []
    for label, y, relation in (('marked', 0, 'inside_authored_marking'),
                               ('outside', 4, 'outside_authored_marking')):
        folder = root / label
        folder.mkdir()
        shutil.copy2(HERE / 'native/road-crosswalk.xodr', folder / 'road-crosswalk.xodr')
        changed = json.loads(json.dumps(rows))
        for row in changed:
            row['pedestrian_xy_m'][1] = y
            for vertex in row['pedestrian_footprint_xy_m']:
                vertex[1] += y
        write_rows(folder / 'curb-samples.jsonl', changed)
        write_context(folder, changed)
        result = measure(folder)
        if result['marking_relation_at_entry'] != relation or result['physical_crossing_observed']:
            raise RuntimeError('Crosswalk branch geometry missed target')
        records.append({'label': label, 'folder': str(folder), 'measurement': result})
    if records[0]['measurement']['vehicle_trace_sha256'] != records[1]['measurement']['vehicle_trace_sha256']:
        raise RuntimeError('Crosswalk controlled vehicle trace differs')
    negatives = []
    for label, error in (('wrong-cell', 'frozen cell'), ('missing-frame', 'Full crosswalk branch'),
                         ('wrong-marking', 'Marked crossing source object')):
        folder = root / label
        shutil.copytree(root / 'marked', folder)
        if label == 'wrong-cell':
            info = json.loads((folder / 'crosswalk-context.json').read_text())
            info['frozen_cell']['control'] = 'crosswalk'
            (folder / 'crosswalk-context.json').write_text(json.dumps(info) + '\n')
        elif label == 'missing-frame':
            changed = rows[:-1]
            write_rows(folder / 'curb-samples.jsonl', changed)
            write_context(folder, changed)
        else:
            tree = ET.parse(folder / 'road-crosswalk.xodr')
            tree.getroot().find('road/objects/object').set('s', '24')
            tree.write(folder / 'road-crosswalk.xodr', encoding='unicode')
            write_context(folder, rows)
        try:
            measure(folder)
        except ValueError as exc:
            if error not in str(exc):
                raise
        else:
            raise RuntimeError('Damaged crosswalk branch accepted: ' + label)
        negatives.append({'label': label, 'folder': str(folder), 'expected_error': error})
    summary = {'format': 'c230222-lvmc-060-a-crosswalk-cpu-construction-v1',
               'crossref_law_id': 'LVMC-11-30-060-A',
               'authored_road': 'native/road-crosswalk.xodr',
               'authored_road_sha256': sha(HERE / 'native/road-crosswalk.xodr'),
               'marking': marking(HERE / 'native/road-crosswalk.xodr'),
               'controlled_variable': 'crossing_y_m', 'records': records,
               'negative_rejections': negatives,
               'physical_crossref_cases_constructed': 0,
               'legal_applicability_conclusion': None,
               'scope': 'Native-authored marked crossing with synthetic source-footprint geometry; no original pixels, right-of-way, designated-place review or legal finding'}
    (HERE / 'crosswalk-branch-summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps({'authored_native_crosswalk_roads': 1, 'controlled_synthetic_cases': 2,
                      'source_negative_rejections': 3, 'physical_crossref_cases_constructed': 0}))


if __name__ == '__main__':
    main()
