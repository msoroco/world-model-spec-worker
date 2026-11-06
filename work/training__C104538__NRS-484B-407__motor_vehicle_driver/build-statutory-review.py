"""Exact frozen-clause branch inventory; no legal applicability conclusion."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
SOURCE=ROOT/'inputs/training__C104538__NRS-484B-407__motor_vehicle_driver/assignment.json'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    assignment=json.loads(SOURCE.read_text())
    law=assignment['law_record']
    if law['id']!='NRS-484B-407' or assignment['cell']['layout']!='hill_crest':
        raise ValueError('Frozen assignment identity differs')
    branches=[
      {'id':'reverse_direction','text_span':'turned so as to proceed in the opposite direction',
       'source_needed':'original Native ego heading, center, footprint and completed maneuver',
       'authored_source_support':'none','physical_observed':False},
      {'id':'curve','text_span':'upon any curve',
       'source_needed':'Native loaded road curvature and maneuver station',
       'authored_source_support':'road.xodr arc proposal','physical_observed':False},
      {'id':'crest','text_span':'upon the approach to or near the crest of a grade',
       'source_needed':'Native loaded elevation, crest station and maneuver station',
       'authored_source_support':'road.xodr elevation proposal','physical_observed':False},
      {'id':'either_direction','text_span':'driver of any other vehicle approaching from either direction',
       'source_needed':'original Native approaching driver viewpoints and target body pixels from both directions',
       'authored_source_support':'two symmetric 500 ft center-reference rays','physical_observed':False},
      {'id':'five_hundred_feet','text_span':'within 500 feet',
       'source_needed':'original Native station/eye/body distances and pixel/occlusion audit',
       'authored_source_support':'fixed 500 ft ray probe against three authored reference limits',
       'physical_observed':False},
    ]
    for branch in branches:
        if branch['text_span'] not in law['text']:
            raise ValueError('Branch span absent from frozen clause: '+branch['id'])
    result={'format':'c104538-frozen-statutory-review-v1',
            'assignment_id':assignment['assignment_id'],
            'frozen_assignment_sha256':sha(SOURCE),
            'law_id':law['id'],'law_text':law['text'],
            'location_alternatives':['curve','crest'],
            'conjunctive_facts':['reverse_direction','either_direction','five_hundred_feet'],
            'branches':branches,'selected_branch':None,
            'native_statutory_coverage_proven':False,'legal_verdict_claimed':False}
    (HERE/'statutory-review.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':print(json.dumps(build(),indent=2))
