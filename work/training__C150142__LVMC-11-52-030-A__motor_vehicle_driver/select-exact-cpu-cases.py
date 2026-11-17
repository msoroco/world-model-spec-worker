"""Select source-backed C150142 CPU cases and rebind their authored bundles.

Selection is a planning decision. It makes no Native observation or readiness
claim, and prior diagnostic receipts remain historical after the rebind.
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False,
                               allow_nan=False) + '\n')


def main():
    plan_path = ROOT / 'case-plan.json'
    plan = json.loads(plan_path.read_text())
    assignment = json.loads((REPO / 'inputs' / ROOT.name / 'assignment.json').read_text())
    witnesses = json.loads((REPO / 'inputs' / ROOT.name / 'witnesses.json').read_text())
    witness = witnesses[0]['witness']
    branch = witness['branch']
    if (len(witnesses) != 1 or witness['decision'] != 'conditional' or
            witness['confidence'] != 'low' or witness.get('recording_ids') or
            plan['scope_branches'] != [branch] or
            assignment['law']['text'] != plan['source_law_text'] or
            len(plan['cases']) != 30):
        raise ValueError('Frozen law, witness, or exact case inventory changed')
    if (REPO / 'inputs' / ROOT.name / 'evidence.json').exists():
        evidence = json.loads((REPO / 'inputs' / ROOT.name / 'evidence.json').read_text())
        if evidence.get('recordings'):
            raise ValueError('Review accepted recordings before new selection')
    old_hash = sha(plan_path)
    if plan['selected_branch'] not in (None, branch):
        raise ValueError('Another witness branch was selected')
    plan['selected_branch'] = branch
    gaps = []
    for item in plan['requirement_dispositions']:
        requirement = item['requirement']
        if not item.get('case_ids'):
            raise ValueError('Requirement has no authored exact case: ' + requirement)
        item['status'] = 'selected_required'
        item['evidence_or_gap'] = (
            'Selected from the frozen full subsection and conditional red-curb '
            'witness for CPU delivery. No accepted recording is supplied; '
            'Native facts, legal applicability, and physical visibility remain unverified.')
        gaps.append({'id': 'gap-' + requirement,
                     'requirement': requirement,
                     'source': item['source'],
                     'why_existing_insufficient':
                     'The frozen assignment has no accepted recording inventory; '
                     'the conditional witness names required context but supplies no Native observation.'})
    gap_ids = {item['requirement']: 'gap-' + item['requirement']
               for item in plan['requirement_dispositions']}
    for case in plan['cases']:
        if case['planning_status'] not in ('unverified_definition',
                                           'selected_cpu_pending_proof'):
            raise ValueError('Unexpected case planning state')
        case['planning_status'] = 'selected_cpu_pending_proof'
        case['gap_ids'] = [gap_ids[topic] for topic in case['source_topic_ids']]
        if 'reviewed-scope-0' in gap_ids:
            case['gap_ids'].append(gap_ids['reviewed-scope-0'])
    plan['evidence_review'] = {
        'method': 'Frozen assignment, witness, and accepted-evidence inventory review',
        'reviewer': 'CPU preparation worker', 'facts': [], 'gaps': gaps,
        'selection_basis': 'Full red-curb subsection including all numbered exceptions; '
                           'conditional witness and no accepted recordings',
        'native_observed': False}
    write(plan_path, plan)
    new_hash = sha(plan_path)
    plan_text = plan_path.read_text()
    manifest_path = ROOT / 'execution-manifest-draft-all.json'
    manifest = json.loads(manifest_path.read_text())
    if len(manifest['cases']) != 30:
        raise ValueError('Integrated exact inventory changed')
    rebound = 0
    for entry in manifest['cases']:
        for candidate in [{'id': 'primary', 'construction': entry['construction']},
                          *entry['candidates']]:
            path = ROOT / candidate['construction']
            package = json.loads(path.read_text())
            if package['case_id'] != entry['case_id']:
                raise ValueError('Wrong exact bundle identity')
            files = {item['path']: item for item in package['files']}
            if files['case-plan.json']['content'] not in (plan_text,):
                old = json.loads(files['case-plan.json']['content'])
                if old['assignment_id'] != plan['assignment_id'] or old['law_id'] != plan['law_id']:
                    raise ValueError('Bundle bound to another plan')
            files['case-plan.json']['content'] = plan_text
            config = json.loads(files['config.json']['content'])
            if config['case_plan_sha256'] not in (old_hash, new_hash):
                raise ValueError('Bundle has an unexpected plan hash')
            config['case_plan_sha256'] = new_hash
            files['config.json']['content'] = json.dumps(config, indent=2,
                                                         ensure_ascii=False) + '\n'
            write(path, package)
            candidate['construction_sha256'] = sha(path)
            rebound += 1
    # Keep the per-family diagnostic manifests source-bound for further proofs.
    for path in sorted(ROOT.glob('execution-manifest-diagnostic-*.json')):
        source = json.loads(path.read_text())
        changed = False
        for entry in source.get('cases', []):
            construction = ROOT / entry.get('construction', '')
            if construction.is_file():
                entry['construction_sha256'] = sha(construction)
                changed = True
            for candidate in entry.get('candidates', []):
                construction = ROOT / candidate.get('construction', '')
                if construction.is_file():
                    candidate['construction_sha256'] = sha(construction)
                    changed = True
        if changed:
            write(path, source)
    native_manifest = ROOT / 'native/manifest.json'
    if native_manifest.exists():
        native = json.loads(native_manifest.read_text())
        native['case_plan_sha256'] = new_hash
        for row in native.get('entries', []):
            slug = row['case_id'].removeprefix(ROOT.name + '__')
            config_path = ROOT / 'native/drafts' / slug / row['candidate_id'] / 'config.json'
            if config_path.exists():
                config = json.loads(config_path.read_text())
                if config.get('case_plan_sha256') not in (old_hash, new_hash):
                    raise ValueError('Native diagnostic config bound to another plan')
                config['case_plan_sha256'] = new_hash
                write(config_path, config)
                row['config_sha256'] = sha(config_path)
        write(native_manifest, native)
    print(json.dumps({'selected_cases': len(plan['cases']),
                      'selected_requirements': len(gaps),
                      'rebound_candidates': rebound,
                      'old_plan_sha256': old_hash, 'new_plan_sha256': new_hash,
                      'native_observed': False}))


if __name__ == '__main__':
    main()
