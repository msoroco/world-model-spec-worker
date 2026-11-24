"""Select distinct hand-signal and officer-direction statutory branches."""
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = HERE.name
SOURCE = 'NRS 484B.267(2)(f); with 484B.267(4)'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def main():
    plan_path = HERE / 'case-plan.json'
    plan = json.loads(plan_path.read_text())
    manifest_path = HERE / 'current-execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    variants = (
        ('visible_hand_signal', 'Visible preparation via source-driver hand signal',
         'draft-hand-signal', 'source-driver hand signal frames 80-99',
         'Review original driver identity, hand pose, recipient sightline and pixels',
         'controlled_1', 'driver_hand_track.jsonl', 'hand_signal_review.json'),
        ('officer_direction', 'Law-enforcement officer otherwise directs driver',
         'draft-officer', 'officer direction frames 100-200',
         'Review original officer identity, direction content, recipient and pixels',
         'controlled_2', 'officer_track.jsonl', 'officer_direction.json'))
    for suffix, branch, draft, difference, gap, baseline, track, review in variants:
        case_id = AID + '__' + suffix
        existing = next((i for i, row in enumerate(plan['requirement_dispositions'])
                         if row['branch'] == branch), None)
        row = {'requirement': 'NRS-484B-267-2f', 'source': SOURCE,
               'branch': branch, 'status': 'selected_required', 'case_ids': [case_id],
               'evidence_or_gap': 'Selected CPU construction requests ' + difference + '. ' + gap + '.'}
        if existing is None:
            index = len(plan['requirement_dispositions'])
            plan['requirement_dispositions'].append(row)
        else:
            index = existing
            plan['requirement_dispositions'][existing] = row
        plan['cases'] = [case for case in plan['cases'] if case['case_id'] != case_id]
        plan['cases'].append({'case_id': case_id, 'target_law_id': plan['law_id'],
                              'kind': 'delivery', 'source_branch': branch,
                              'physical_target': difference + '; ' + gap,
                              'comparison_variable': difference,
                              'requested_not_measured': True,
                              'selection_targets': ['full-train'],
                              'gap_ids': ['approaching_referral']})
        comparison_id = AID + '__' + suffix + '_comparison'
        plan['comparisons'] = [c for c in plan['comparisons']
                               if c['comparison_id'] != comparison_id]
        plan['comparisons'].append({'comparison_id': comparison_id,
            'case_ids': [AID + '__' + baseline, case_id],
            'deliberate_differences': [difference],
            'fixed_conditions': ['same road, source vehicle, original ego path request, flashing-light program and four camera timing']})
        base = next(entry for entry in manifest['cases']
                    if entry['case_id'] == AID + '__' + baseline)
        entry = copy.deepcopy(base)
        entry['case_id'] = case_id
        entry['construction'] = draft + '/primary/construction.json'
        entry['construction_sha256'] = sha(HERE / entry['construction'])
        entry['measurement_contract'] = 'current-contracts/' + suffix + '.json'
        entry['fixture_recipe'] = 'work/' + AID + '/' + draft + '/recipe.json'
        entry['candidate_risk'] = {'status': 'none',
            'reason': 'One direct source-shaped pose request tests this alternative; no distinct physical fallback trigger identified'}
        entry['candidates'] = []
        for key in ('physical_preparation', 'offline', 'compatibility', 'negative',
                    'saved_processing', 'post_capture', 'delivery_acceptance', 'acquisition'):
            entry.pop(key, None)
        manifest['cases'] = [e for e in manifest['cases']
                             if e['case_id'] != case_id] + [entry]
        contract = {'format': 'worker-measurement-contract', 'requirements': [
            {'disposition_index': index, 'requirement': 'NRS-484B-267-2f',
             'source': SOURCE, 'output_key': 'approach_response',
             'method': 'measure_approach_response', 'value_type': 'object',
             'kind': 'measured',
             'inputs': ['video_frames.jsonl', 'vehicle_poses.jsonl',
                        'emergency_context.json', track, review]}],
            'negative': {'remove': [track],
                         'error_contains': 'Missing required source: ' + track}}
        write(HERE / entry['measurement_contract'], contract)
    manifest['delivery_ready'] = False
    write(plan_path, plan)
    write(manifest_path, manifest)
    print(json.dumps({'selected_cases': [AID + '__' + v[0] for v in variants]}))


if __name__ == '__main__':
    main()
