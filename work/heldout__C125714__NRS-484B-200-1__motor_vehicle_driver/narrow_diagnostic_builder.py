"""Build a synthetic narrow-road saved-source diagnostic from the left control."""

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path


CASE='heldout__C125714__NRS-484B-200-1__motor_vehicle_driver__insufficient_width'


def build(left):
    result=deepcopy(left)
    files=result['files']
    rows=[json.loads(line) for line in files['directed_roadway_footprints.jsonl'].splitlines() if line]
    if not rows:
        raise ValueError('Original directed road fixture missing')
    for row in rows:
        if row['travel_tangent_xy'] != [1.0,0.0] or row['roadway_center_point_xy'] != [0.0,0.0]:
            raise ValueError('Narrow diagnostic expects eastbound fixed section')
        row['left_road_edge_xy']=[0.0,-2.2]
        row['right_road_edge_xy']=[0.0,2.2]
        row['subject_lane_width_m']=2.2
        row['opposite_lane_width_m']=2.2
    files['directed_roadway_footprints.jsonl']=''.join(json.dumps(row)+'\n' for row in rows)
    manifest=json.loads(files['capture/manifest.json'])
    manifest['case_id']=CASE
    files['capture/manifest.json']=json.dumps(manifest,indent=2)+'\n'
    files['narrow-width-diagnostic-provenance.json']=json.dumps({
        'format':'worker-diagnostic-source-note',
        'use':'synthetic 4.4 m road cross-section for CPU processing only',
        'legal_sufficiency_decided':False,'physical_acceptance_claimed':False,
        'builder':'narrow_diagnostic_builder.py'},indent=2)+'\n'
    return result


def main():
    root=Path(__file__).parent
    output=root/'narrow-diagnostic.json'
    if output.exists():
        raise ValueError('Retain prior narrow diagnostic')
    output.write_text(json.dumps(build(json.loads((root/'left-diagnostic.json').read_text())),
                                 allow_nan=False)+'\n')


if __name__=='__main__':
    main()
