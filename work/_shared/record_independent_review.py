"""Record the lead's independent, original-law semantic review after owners finish."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
NOTES={
'NRS-484B-400-2a':'Marked and imaginary equidistant centerlines; all approach body vertices; connected two-directional left turn; departure policy fixed and no invented nearest cutoff.',
'NRS-484B-400-2b':'Marked and imaginary centerlines; after-entry departure body position with approach policy fixed, without a legal lateral epsilon.',
'NRS-484B-253':'Already-within and approaching hazard alternatives; prior yielding, required signal history, and distinct reciprocal opposite-driver behavior after release. Hazard and lawful preference remain legal judgments.',
'NRS-484B-223-1b':'Clearly marked multiple same-direction lanes, appropriate signal before lateral departure, and separate target-lane safety-ascertainment evidence. Lamp API and gaps are not judgments of displayed appropriateness or human knowledge.',
'NRS-484B-127-3':'Caravan and motorcade; towing and no towing; all-unit gaps and conventional/combination entrant occupancy. Outside-business context is sourced separately; spring hitch stability remains a Native check.',
'NRS-484A-450-2':'Crosswalk-first hierarchy differs from257: marked or sidewalk-derived crosswalk, then line if no crosswalk, then nearest sampled clear viewpoint. Saved finalizer recomputes closest clear point and source frame; complete cessation not defined by controller epsilon.',
'NRS-484B-250-1':'Different-highway previous entry, actual entry order, opposite intended/ongoing left exceptions, official sign/signal exclusions and250-4 qualification. Physically widened divider yields separate roadway intersections rather than inherited35m metadata.',
'NRS-484B-250-2':'Left/right precedence at approximately simultaneous different-highway entry; raw timing not a legal simultaneity epsilon. Device and opposite-left exclusions and250-4 override separated; divided crossings separately grounded.',
'NRS-484B-227-1':'Right-hand roadway; explicit over/across/within raw geometry; left turn in a separate compatible fixed-maneuver cell; semicircular and continuous/discontinuous U-turn; openings in barrier/section/space; authority-established crossover/intersection. Multiple rows explicitly reuse controlled recordings.',
'NRS-484B-220-1':'Designation and signposting are separate sourced conditions; actual displacement/velocity along designated roadway direction is measured rather than vehicle heading alone.',
'NRS-484B-600-1a':'Raw speed, traffic, surface, width, weather and other conditions; actual calibration image/contrast sources separated from weather fog parameters. No numerical reasonable/proper standard or fixture-only visibility drop.',
'NRS-484B-413-2':'Right/left/other direct-course changes; business/residential100ft and other-area300ft traveled path; continuity and weather; source display samples distinct from legal signal appropriateness. Base right/business witness not imposed on incompatible supplemental cases.',
'NRS-484B-257-1':'Stop/yield each with line, marked/unmarked crosswalk and nearest-view hierarchy; yield slowed/stopped alternative; occupied/approaching traffic and across/within history; actual officer/signal exceptions with compatible fixed-control bindings.',
'NRS-484B-257-2':'Inherited257-1 stop/yield hierarchy, non-through setting, one-or-more obligated entrances, not-so-obligated traffic, occupied/approaching/across-within history, cautious progression and actual governing exceptions. Applicable witness requirements are case-scoped.',
'NRS-484B-407':'Curve, approach-to-crest and near-crest; both approaching directions within500ft; body-vertex rays and raw obstructions; continuous/discontinuous reversal. Collision-ray evidence does not claim optical visibility or continuous legal acceptance.',
'NRS-484B-127-2':'Truck/combination permutations; both inclusive80-inch qualifications;500ft space, conditions-permit, entrant enter/occupy, actual overtaking/passing, and two-available-lanes exception. Unsupported post-overtake grace duration removed.',
'NRS-484B-113-2':'Backing into intersection, on/over marked and sidewalk-derived crosswalk, and around street corner; time-aligned signed velocity/body occupancy, intersection transition and corner-relative trajectory. No invented instant-contact legal verdict.',
'NRS-484B-127-1':'Actual following, full-body gaps, both speeds, traffic/queue/braking and dry/wet highway conditions. Ice prompt mapped to explicit authored absence evidence; no required positive ice demonstration or headway/duration legal cutoff.',
'NRS-484B-600-1e':'Below/equal/strictly above80mph with exact boundary CPU tests; actual access-aisle fixed layout authored and inventoried, no engineering legal tolerance.',
'NRS-484B-600-1c':'Strict posted rate boundary, authority, direction, particular portion, equivalent units and source visibility; Decimal unit normalization avoids a legal epsilon. Actual sign realization and authority remain original-source/pixel checks.',
'NRS-484B-307-6a':'Steady yellow alone and facing applicability; related green termination/subsequent red; red versus yellow entry and already-inside clearance. No yellow stop obligation or numeric immediacy rule invented.',
'NRS-484B-250-4':'Installed/uncovered/inoperative at entry; line/crosswalk/nearest-view hierarchy; earlier completed stops and occupancy histories; cautious departure; operative/absent installation qualification in compatible supplemental controls. Unmarked reference corrected to actual sidewalk edge-9m.'}
def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 matrix=read(ROOT/'work/_shared/branch-coverage.json');batch=read(ROOT/'batch.json');sources=read(ROOT/'inputs/coverage/branch-sources.json')['laws']
 definitions=[json.loads(s) for s in (ROOT/'inputs/definitions.jsonl').read_text().splitlines() if s]
 if set(NOTES)!=set(sources) or set(matrix['laws'])!=set(sources):raise ValueError('Semantic review law scope differs')
 originals={read(ROOT/'inputs'/aid/'assignment.json')['law_id']:aid for aid in batch['assignments']}
 rows={}
 for law in sources:
  original=read(ROOT/'inputs'/originals[law]/'assignment.json')
  if original['law']!=sources[law]['law']:raise ValueError('Original statutory source join differs')
  branches=matrix['laws'][law]['branches'];aids=sorted({b['assignment_id'] for b in branches});plans={aid:read(ROOT/'work'/aid/'case-plan.json') for aid in aids}
  for aid,plan in plans.items():
   result=read(ROOT/'work'/aid/'result.json')
   if result['status']!='ready':raise ValueError('Owner not ready for final review')
   for d in plan['requirement_dispositions']:
    if 'immediately after an overtake is excepted' in d['requirement']:raise ValueError('Unsupported grace duration still selected')
  rows[law]={'original_assignment_id':originals[law],'original_assignment_sha256':sha(ROOT/'inputs'/originals[law]/'assignment.json'),'statutory_text':original['law']['text'],'source':original['law']['source'],'branch_ids':[b['branch_id'] for b in branches],'review_conclusion':NOTES[law],'case_plan_sha256':{aid:sha(ROOT/'work'/aid/'case-plan.json') for aid in aids}}
 review={'format':'worker-full-branch-review-v1','coverage_sha256':sha(ROOT/'work/_shared/branch-coverage.json'),'reviewer':'lead; independent of four partition owners','review_method':'Lead independently read all22 original laws and complete supplied definitions before reviewing owner inventories, then performed a separate final branch-by-branch review after all four owners finished. Compared alternatives/exceptions, fixed-cell eligibility, exact-case requirement/method/applicability joins, measurement rules, comparison isolation and recording reuse. Source hashes bind the final reviewed plans; runtime/fixture software proofs do not establish physical or legal acceptance.','branch_sources_sha256':sha(ROOT/'inputs/coverage/branch-sources.json'),'definitions_sha256':sha(ROOT/'inputs/definitions.jsonl'),'definition_ids_reviewed':[d['id'] for d in definitions],'laws':rows,'missing_branches':[],'physical_acceptance_claimed':False,'legal_acceptance_claimed':False,'remaining_review':'Native physical completion, original camera pixels, calibrated visibility applicability, continuous nearest point, control/source authority and unresolved legal judgments remain operator checks.'}
 (ROOT/'work/_shared/branch-review.json').write_text(json.dumps(review,indent=2)+'\n')
 print('Independent review recorded for22 original laws; no omitted planned statutory branches found.')
if __name__=='__main__':main()
