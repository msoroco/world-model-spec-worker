"""Independent frozen-law and source-topic scope audit for the corner assignment."""
import hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
def main():
    assignment_path=ROOT/'inputs'/HERE.name/'assignment.json'
    assignment=json.loads(assignment_path.read_text())
    review=json.loads((HERE/'statutory-review.json').read_text())
    if review['assignment_sha256']!=hashlib.sha256(assignment_path.read_bytes()).hexdigest() or review['exact_text']!=assignment['law_record']['text']:
        raise ValueError('Statutory source binding differs')
    if (assignment['cell']['layout'],assignment['cell']['maneuver'],assignment['cell']['control'])!=('intersection','reverse','street_corner'):
        raise ValueError('Frozen corner cell differs')
    branches={row['branch']:row['frozen_cell'] for row in review['branches']}
    if branches!={'back into an intersection':'C110763','on or over a crosswalk':'C110741','around a street corner':'C110812'}:
        raise ValueError('Three statutory branches not distinguished')
    plan=json.loads((HERE/'case-plan.json').read_text())
    topics=plan['requirement_dispositions']
    if [r['requirement'] for r in topics]!=['text-0','text-1','reviewed-scope-0','reviewed-scope-1','reviewed-scope-2']:
        raise ValueError('Exported source topics differ')
    if not all('crosswalk' in r['evidence_or_gap'] for r in topics[2:]) or 'crosswalk' not in review['source_topic_conflict']:
        raise ValueError('Crosswalk/corner source-topic conflict hidden')
    if review['ready'] is not False:raise ValueError('Unproven statutory review marked ready')
    print(json.dumps({'passed':True,'assignment_sha256':review['assignment_sha256'],
                      'branch_cells':branches,'reviewed_scope_topics_are_crosswalk':True,
                      'corner_authority':'exact subsection text and frozen corner witness only',
                      'ready':False},indent=2))
if __name__=='__main__':main()
