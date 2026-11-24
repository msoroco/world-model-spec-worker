"""Check the authored 287(c) marking comparison and fixture source joins."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(ok, message):
    if not ok:
        raise ValueError(message)


def main():
    plan = json.loads((ASSIGNMENT / 'case-plan.json').read_text())
    pair_id = ASSIGNMENT.name + '__crossref_287c_marking_comparison'
    pair = next(x for x in plan['comparisons'] if x['comparison_id'] == pair_id)
    expected = [ASSIGNMENT.name + '__crossref_287c_' + x for x in ('marked', 'unmarked')]
    require(pair['case_ids'] == expected and
            pair['deliberate_differences'] == ['marked_midblock_crossing_target'],
            '287(c) comparison plan differs')
    contexts = []
    inventories = []
    for label, case_id in zip(('marked', 'unmarked'), expected):
        recipe = json.loads((HERE / label / 'recipe.json').read_text())
        inventory = {x['path']: x['sha256'] for x in recipe['sources']}
        context_path = HERE / label / 'sources/curb-context.json'
        require(inventory['curb-context.json'] == sha(context_path),
                '287(c) fixture context hash differs')
        context = json.loads(context_path.read_text())
        require(context['source_kind'] == 'synthetic_scene_request' and
                context['authored_marked_crossing_target'] == (label == 'marked'),
                '287(c) authored marking target differs')
        contexts.append(context)
        inventories.append(inventory)
        contract = json.loads((HERE / label / 'measurement-contract.json').read_text())
        require(contract['case_id'] == case_id and
                contract['negative']['remove'] == ['curb-samples.jsonl'],
                '287(c) exact-case negative contract differs')
    for inventory in inventories:
        inventory.pop('curb-context.json')
        inventory.pop('capture/manifest.json')
    require(inventories[0] == inventories[1],
            '287(c) fixture changed a supposedly fixed acquisition source')
    for context in contexts:
        context.pop('authored_road_sha256')
        context.pop('authored_marked_crossing_target')
    require(contexts[0] == contexts[1],
            '287(c) fixture context changed beyond marking and authored road')
    proof = json.loads((HERE / 'source-proof.json').read_text())
    require([x['case_id'] for x in proof['cases']] == expected and
            not proof['operating_official_devices_verified'] and
            not proof['original_marking_pixels_verified'],
            '287(c) authored source proof or limits differ')
    receipt = {'format': 'c230222-287c-authored-comparison-v1',
               'comparison_id': pair_id, 'case_ids': expected,
               'fixed_fixture_sources_sha256': inventories[0],
               'source_proof_sha256': sha(HERE / 'source-proof.json'),
               'case_plan_sha256': sha(ASSIGNMENT / 'case-plan.json'),
               'native_executed': False,
               'original_device_operation_and_marking_verified': False,
               'legal_applicability_conclusion': None}
    target = HERE / 'comparison-proof.json'
    target.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'comparison_id': pair_id, 'sha256': sha(target)}))


if __name__ == '__main__':
    main()
