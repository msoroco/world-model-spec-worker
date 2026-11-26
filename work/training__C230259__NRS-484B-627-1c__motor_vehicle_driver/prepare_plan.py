"""Bind frozen route requests to executable channels without claiming outcome."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLAN = HERE / 'case-plan.json'
ASSIGNMENT = HERE.name


def main():
    plan = json.loads(PLAN.read_text())
    plan['selected_branch'] = plan['witness_branches'][0]
    for disposition in plan['requirement_dispositions']:
        disposition['status'] = 'selected_required'
        disposition['evidence_or_gap'] = ('Executable exact route attempt with source-bound original '
            'position, actor, road topology and time channels; physical and legal facts await local review.')
    for case in plan['cases']:
        case['kind'] = 'delivery'
        case['requested_not_measured'] = True
        case['gap_ids'] = ['unobserved_route_context']
    plan['evidence_review'] = {'reviewer': 'worker CPU source review',
        'method': 'Read frozen assignment, witness and empty accepted-recording inventory; '
                  'no original accepted recordings are supplied for this exact assignment.',
        'facts': [], 'gaps': [{'id': 'unobserved_route_context',
            'requirement': 'NRS-484B-627-1c', 'source': 'NRS 484B.627(1)(c)',
            'why_existing_insufficient': 'No accepted recording establishes a controlled-access '
                'designation, immediately following impeded traffic, or a possible route and its use.'}]}
    channels = {
        'drv.speed_below_traffic': ['participant_motion'],
        'drv.queue_behind': ['participant_motion'],
        'st.controlled_access': ['route_occupancy'],
        'st.lane_connectivity': ['route_occupancy'],
        'kin.path_length': ['route_occupancy', 'participant_motion'],
        'rel.occupies': ['route_occupancy'],
    }
    evidence = {
        'drv.speed_below_traffic': 'Actual same-frame subject/follower speeds and controller free-flow intent; legal impediment requires review.',
        'drv.queue_behind': 'Original actor IDs, positions, lanes and order on the approach; queue judgment requires review.',
        'st.controlled_access': 'Original road IDs joined to a separate designation source; no designation source is supplied yet.',
        'st.lane_connectivity': 'Original OpenDRIVE branches and per-frame road occupancy; practical route usability remains unverified.',
        'kin.path_length': 'Original route trace positions and duration; travel distance can be derived without a legal threshold.',
        'rel.occupies': 'Original road ID occupancy on main or alternate route with camera/frame joins.'}
    plan['source_observation_mapping'] = {term: {'evidence': evidence[term],
        'channels': names, 'source_refs': [
            'inputs/' + ASSIGNMENT + '/assignment.json',
            'route-trace.jsonl', 'route-context.json', 'road.xodr']}
        for term, names in channels.items()}
    plan['observations'] = [
        {'name': 'participant_motion', 'mandatory': True,
         'reason': 'same-frame motor vehicle driver and immediate follower motion'},
        {'name': 'route_occupancy', 'mandatory': True,
         'reason': 'original route topology and observed road occupancy'}]
    plan['mandatory_observation_terms'] = [
        {'term': term, 'purpose': evidence[term], 'status': 'mapped_to_source_channel'}
        for term in channels]
    plan['candidate_plans'] = [{'case_id': case['case_id'],
        'primary': 'draft-route/' + case['case_id'].rsplit('__', 1)[-1] + '/primary/construction.json',
        'fallback1': 'draft-route/' + case['case_id'].rsplit('__', 1)[-1] + '/fallback1/construction.json',
        'risk': 'Native route-turn or lane-following deviation needs local check'}
        for case in plan['cases']]
    plan['blockers'] = ['Selected positive/negative compatibility, saved-only processing, '
        'semantic proposals, physical/lifecycle proofs and independent delivery/comparison audits remain CPU work.']
    plan['readiness_limitation'] = 'Executable Native drafts and offline proofs; no physical or legal outcome claimed.'
    PLAN.write_text(json.dumps(plan, indent=2) + '\n')
    proposal = {'cell_id': 'C230259', 'actor': 'motor_vehicle_driver',
        'status': 'source-shaped CPU construction', 'cases': plan['cases']}
    target = HERE / 'proposals' / 'cases.json'
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(proposal, indent=2) + '\n')
    print(json.dumps({'cases': len(plan['cases']), 'channels': len(plan['observations'])}))


if __name__ == '__main__':
    main()
