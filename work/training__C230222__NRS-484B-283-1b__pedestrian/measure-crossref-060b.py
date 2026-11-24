"""Source-bound synthetic overhead survey target measurement, without physical claim."""
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
LABELS = ('overhead_candidate', 'no_overhead')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def measure(label, rows_override=None):
    folder = HERE / 'crossref-060b-native' / label
    construction = json.loads((folder / 'construction.json').read_text())
    files = {item['path']: item['content'] for item in construction['files']}
    root = ET.fromstring(files['road.xodr'])
    objects = root.findall('.//objects/object')
    samples = folder / 'fixture-sources/curb-samples.jsonl'
    rows = [json.loads(line) for line in samples.read_text().splitlines()] if rows_override is None else rows_override
    if len(rows) != 600 or any(row['native_frame'] != 100 + i for i, row in enumerate(rows)):
        raise ValueError('600 contiguous original-frame diagnostic source rows required')
    first = next((row for row in rows if row['pedestrian_xy_m'][0] >= -3.5), None)
    if first is None:
        raise ValueError('No source roadway entry')
    present = len(objects) == 1 and objects[0].get('type') == 'bridge'
    if present != (label == 'overhead_candidate'):
        raise ValueError('Authored overhead survey target relation differs')
    vehicle = [(row['native_frame'],row['time_s'],row['vehicle_xy_m']) for row in rows]
    vehicle_hash = hashlib.sha256(json.dumps(vehicle,sort_keys=True).encode()).hexdigest()
    return {'format':'c230222-060b-synthetic-infrastructure-measurement-v1',
            'case_id':construction['case_id'],'source_kind':'synthetic_scene_request',
            'source_sha256':{'curb-samples.jsonl':digest(samples),
                             'road.xodr':hashlib.sha256(files['road.xodr'].encode()).hexdigest()},
            'frames':600,'roadway_entry_frame':first['native_frame'],
            'authored_bridge_type_survey_target_present':present,
            'vehicle_trace_sha256':vehicle_hash,
            'native_rendered_pedestrian_overhead_verified':False,
            'usable_pedestrian_access_verified':False,
            'original_pixels_verified':False,
            'vehicle_right_of_way_reviewed':False,
            'designated_place_prohibition_reviewed':False,
            'legal_applicability_conclusion':None}


if __name__ == '__main__':
    values=[]
    for label in LABELS:
        value=measure(label)
        path=HERE/'crossref-060b-native'/label/'source-measurement.json'
        path.write_text(json.dumps(value,indent=2)+'\n')
        values.append(value)
    if values[0]['vehicle_trace_sha256'] != values[1]['vehicle_trace_sha256'] or values[0]['roadway_entry_frame'] != values[1]['roadway_entry_frame']:
        raise ValueError('Controlled source trace or timing differs')
    sample = HERE / 'crossref-060b-native/overhead_candidate/fixture-sources/curb-samples.jsonl'
    truncated = [json.loads(line) for line in sample.read_text().splitlines()][:-1]
    try:
        measure('overhead_candidate', rows_override=truncated)
    except ValueError as error:
        if '600 contiguous' not in str(error):
            raise
    else:
        raise ValueError('Missing-frame negative was accepted')
    print(json.dumps({'source_measurements':len(values),'fixed_vehicle_trace':True,
                      'missing_frame_rejected':True,'overhead_physically_verified':False}))
