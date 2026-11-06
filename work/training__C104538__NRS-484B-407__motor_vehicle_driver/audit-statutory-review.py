"""Independent exact-source and branch completeness check for the draft review."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]


def audit():
    source=ROOT/'inputs/training__C104538__NRS-484B-407__motor_vehicle_driver/assignment.json'
    original=json.loads(source.read_text())
    review=json.loads((HERE/'statutory-review.json').read_text())
    assert review['frozen_assignment_sha256']==hashlib.sha256(source.read_bytes()).hexdigest()
    assert review['assignment_id']==original['assignment_id']
    assert review['law_id']==original['law_record']['id']
    assert review['law_text']==original['law_record']['text']
    branches={row['id']:row for row in review['branches']}
    assert set(branches)=={'reverse_direction','curve','crest','either_direction','five_hundred_feet'}
    assert set(review['location_alternatives'])=={'curve','crest'}
    assert set(review['conjunctive_facts'])=={'reverse_direction','either_direction','five_hundred_feet'}
    assert all(row['text_span'] in review['law_text'] and row['source_needed'] and
               row['physical_observed'] is False for row in branches.values())
    assert review['selected_branch'] is None
    assert review['native_statutory_coverage_proven'] is False
    assert review['legal_verdict_claimed'] is False
    return {'passed':True,'frozen_clause_exact':True,'branch_count':5,
            'physical_branch_observations':0,'selected_branch':None}


if __name__=='__main__':print(json.dumps(audit(),indent=2))
