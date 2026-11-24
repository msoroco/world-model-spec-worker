"""Bind 600-frame marked versus outside crossing source and offline proofs."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BASE = HERE / 'crossref-060a-native'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def main():
    original = HERE / 'v2-primary/probe_1/sources/curb-samples.jsonl'
    rows = [json.loads(line) for line in original.read_text().splitlines()]
    if len(rows) != 600:
        raise ValueError('Primary 600-frame source unavailable')
    measurement_source = (HERE / 'native/crosswalk_branch.py').read_text()
    if measurement_source.count('len(rows) != 240') != 1:
        raise ValueError('Unexpected crosswalk measurement source')
    measurement_source = measurement_source.replace('len(rows) != 240', 'len(rows) != 600')
    (BASE / 'measure.py').write_text(measurement_source)
    sys.path.insert(0, str(BASE))
    from measure import measure
    records = []
    for label, y, relation in (('marked', 0, 'inside_authored_marking'),
                               ('outside', 4, 'outside_authored_marking')):
        folder = BASE / label / 'sources'
        folder.mkdir(parents=True, exist_ok=True)
        shutil.copy2(HERE / 'native/road-crosswalk.xodr', folder / 'road-crosswalk.xodr')
        changed = json.loads(json.dumps(rows))
        for row in changed:
            row['pedestrian_xy_m'][1] = y
            for vertex in row['pedestrian_footprint_xy_m']:
                vertex[1] = y + vertex[1]
        sample = folder / 'curb-samples.jsonl'
        sample.write_text(''.join(json.dumps(row, separators=(',', ':')) + '\n' for row in changed))
        write(folder / 'crosswalk-context.json', {
            'source_kind': 'synthetic_scene_request',
            'frozen_cell': {'layout': 'road', 'maneuver': 'travel', 'control': 'curb'},
            'road_sha256': sha(folder / 'road-crosswalk.xodr'),
            'curb_samples_sha256': sha(sample),
            'pedestrian_id': rows[0]['pedestrian_id'],
            'vehicle_id': rows[0]['vehicle_id'],
            'marked_crosswalk_pixel_status': 'unobserved',
            'designated_place_prohibition': 'unreviewed'})
        result = measure(folder)
        if result['frames'] != 600 or result['marking_relation_at_entry'] != relation or result['physical_crossing_observed']:
            raise ValueError('Crosswalk source measurement differs: ' + label)
        write(BASE / label / 'source-measurement.json', result)
        offline = ROOT / '.runtime-work' / f'c230222-crossref-060a-{label}-offline4/offline.log'
        if not offline.is_file() or '\nOK\n' not in offline.read_text():
            raise ValueError('Crosswalk Native offline proof missing: ' + label)
        (BASE / label / 'offline.log').write_text(offline.read_text().rstrip('\n') + '\n')
        construction = BASE / label / 'construction.json'
        records.append({'case_id': HERE.name + '__crossref_lvmc_11_30_060_a_' + label,
                        'construction_sha256': sha(construction),
                        'offline_log_sha256': sha(BASE / label / 'offline.log'),
                        'source_measurement_sha256': sha(BASE / label / 'source-measurement.json'),
                        'marking_relation': relation,
                        'vehicle_trace_sha256': result['vehicle_trace_sha256']})
    if records[0]['vehicle_trace_sha256'] != records[1]['vehicle_trace_sha256']:
        raise ValueError('Crosswalk pair vehicle trace differs')
    with tempfile.TemporaryDirectory(dir=ROOT / '.runtime-work', prefix='c230222-crossref-negative-') as temp:
        folder = Path(temp)
        shutil.copytree(BASE / 'marked/sources', folder / 'missing-frame')
        sample = folder / 'missing-frame/curb-samples.jsonl'
        sample.write_text('\n'.join(sample.read_text().splitlines()[:-1]) + '\n')
        context = folder / 'missing-frame/crosswalk-context.json'
        info = json.loads(context.read_text())
        info['curb_samples_sha256'] = sha(sample)
        write(context, info)
        try:
            measure(folder / 'missing-frame')
        except ValueError as error:
            if 'Full crosswalk branch source required' not in str(error):
                raise
        else:
            raise ValueError('Missing-frame crosswalk source accepted')
    summary = {'format': 'c230222-crossref-060a-native-cpu-proof-v1',
               'crossref_law_id': 'LVMC-11-30-060-A',
               'source_measurement_script': 'crossref-060a-native/measure.py',
               'source_measurement_sha256': sha(BASE / 'measure.py'),
               'records': records, 'missing_frame_rejected': True,
               'original_native_observed': False, 'legal_applicability_conclusion': None}
    write(BASE / 'proof.json', summary)
    print(json.dumps({'offline_cases': 2, 'source_measurements': 2,
                      'missing_frame_rejections': 1}))


if __name__ == '__main__':
    main()
