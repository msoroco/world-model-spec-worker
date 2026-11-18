"""Full-law planning contract shared by worker and local takeover."""
from pathlib import Path
from .common import read, sha, within, assignment_id


def assignments(repo, batch):
    result = dict(batch['assignments'])
    path = Path(repo)/'work/_shared/branch-coverage.json'
    if not batch.get('full_branch_coverage_required') or not path.exists():
        return result
    candidates = {c['cell_id']: c for c in read(Path(repo)/'inputs/coverage/candidate-cells.json')['cells']}
    for binding in read(path).get('additional_bindings', []):
        aid = binding['assignment_id']
        if aid in result: raise ValueError('Duplicate supplemental binding')
        source = within(repo, 'work/'+aid+'/assignment.json')
        a = read(source)
        original = read(Path(repo)/'inputs'/binding['original_assignment_id']/'assignment.json')
        cell = candidates.get(a['cell_id'])
        role = original['role']
        forbidden_sets = ({'full-train', 'demo-train', 'held-out'} if role == 'testing'
                          else {'full-test', 'demo-test', 'held-out'} if role == 'training'
                          else {'full-train', 'demo-train', 'full-test', 'demo-test'})
        if (assignment_id(a,role) != aid or a.get('role') != role or
                a['law_id'] != original['law_id'] or not cell or
                a['actor'] not in cell['candidate_ego_parties'] or
                any(s in cell['allocated_sets'] for s in forbidden_sets)):
            raise ValueError('Ineligible supplemental binding')
        if not binding.get('original_cell_incompatibility') or not binding.get('binding_reason'):
            raise ValueError('Changing cells requires original-cell incompatibility and binding review')
        result[aid] = {'input_sha256': sha(source), 'supplemental': True}
    return result


def assignment_path(repo, aid, item):
    return Path(repo)/('work' if item.get('supplemental') else 'inputs')/aid/'assignment.json'


def validate_evidence(repo, aid, plan, no_capture=False):
    """Require explicit source-reviewed gaps/reuses, not a generic novelty claim."""
    repo = Path(repo)
    inventory_path = repo/'inputs'/aid/'evidence.json'
    inventory = read(inventory_path) if inventory_path.exists() else {'recordings': []}
    accepted = {r['recording_id']: r for r in inventory['recordings']}
    if not accepted and not no_capture:
        return
    review = plan.get('evidence_review', {})
    if not review.get('method') or not review.get('reviewer'):
        raise ValueError('Missing existing-evidence review: '+aid)
    facts = review.get('facts', [])
    reviewed = set()
    for fact in facts:
        rid = fact.get('recording_id')
        if rid not in accepted or not fact.get('demonstrated_fact') or not fact.get('limitations'):
            raise ValueError('Incomplete accepted-evidence fact: '+aid)
        refs = fact.get('sources', [])
        if not refs or any(ref not in accepted[rid]['sources'] or
                sha(within(repo, ref['path'])) != ref['sha256'] for ref in refs):
            raise ValueError('Accepted-evidence fact lacks frozen source bindings: '+aid)
        reviewed.add(rid)
    if reviewed != set(accepted):
        raise ValueError('Existing accepted recordings left unreviewed: '+aid)
    gaps = review.get('gaps')
    if not isinstance(gaps, list):
        raise ValueError('Missing explicit evidence gaps: '+aid)
    gap_ids = set()
    for gap in gaps:
        if not gap.get('id') or gap['id'] in gap_ids or not gap.get('requirement') or not gap.get('source') or not gap.get('why_existing_insufficient'):
            raise ValueError('Incomplete or duplicate evidence gap: '+aid)
        gap_ids.add(gap['id'])
    if no_capture:
        if gaps or not facts or plan['cases'] or plan['comparisons']:
            raise ValueError('No-new-capture disposition requires reviewed evidence and no gaps/cases: '+aid)
    elif not gaps or any(not set(case.get('gap_ids', [])) or not set(case['gap_ids']) <= gap_ids for case in plan['cases']):
        raise ValueError('New case must address identified existing-evidence gaps: '+aid)


def validate(repo, batch, items, require_ready=False):
    repo = Path(repo)
    matrix = read(repo/'work/_shared/branch-coverage.json')
    sources = read(repo/'inputs/coverage/branch-sources.json')['laws']
    if matrix.get('format') != 'worker-full-branch-coverage' or matrix.get('batch_id') != batch['batch_id']:
        raise ValueError('Wrong full branch coverage identity')
    laws = matrix.get('laws', {})
    if set(laws) != set(sources): raise ValueError('Every exported law needs a full branch inventory')
    all_cases = set(); blocked = []
    for law, source in sources.items():
        covered = set(); branches = laws[law].get('branches', [])
        if not branches: raise ValueError('Law has no statutory branch inventory: '+law)
        for branch in branches:
            topics = set(branch.get('topic_ids', []))
            if not topics or not topics <= set(source['topics']): raise ValueError('Branch has missing or invented source topics')
            covered |= topics
            if branch.get('status') == 'capability_blocked':
                proof = within(repo, branch['blocker_receipt'])
                if sha(proof) != branch.get('blocker_sha256') or not read(proof).get('tested_limitation'):
                    raise ValueError('Unsupported branch needs a tested capability blocker')
                blocked.append(branch['branch_id']); continue
            if branch.get('status') == 'existing_evidence':
                aid = branch.get('assignment_id')
                if aid not in items:
                    raise ValueError('Existing-evidence branch has undefined assignment')
                a = read(assignment_path(repo, aid, items[aid]))
                if a['law_id'] != law:
                    raise ValueError('Existing evidence bound to another law')
                plan = read(repo/'work'/aid/'case-plan.json')
                validate_evidence(repo, aid, plan, no_capture=True)
                inventory = read(repo/'inputs'/aid/'evidence.json')
                accepted = {r['recording_id'] for r in inventory['recordings']}
                if not branch.get('recording_ids') or not set(branch['recording_ids']) <= accepted or not branch.get('coverage_reason'):
                    raise ValueError('Existing-evidence branch lacks accepted recordings and coverage reason')
                continue
            if branch.get('status') != 'runnable': raise ValueError('Branch cannot be left pending')
            aid = branch['assignment_id']
            if aid not in items: raise ValueError('Branch names an undefined binding')
            a = read(assignment_path(repo, aid, items[aid]))
            if a['law_id'] != law: raise ValueError('Branch bound to another law')
            plan = read(repo/'work'/aid/'case-plan.json')
            cases = {c['case_id'] for c in plan['cases']}
            selected = set(branch.get('case_ids', []))
            comparisons = {c['comparison_id']: c for c in plan['comparisons']}
            if len(selected) < 2 or not selected <= cases or not branch.get('comparison_ids'):
                raise ValueError('Every runnable branch needs executable comparison cases')
            for cid in branch['comparison_ids']:
                if cid not in comparisons or not selected <= set(comparisons[cid]['case_ids']):
                    raise ValueError('Branch comparison does not contain its cases')
            all_cases |= selected
        if covered != set(source['topics']): raise ValueError('Unmapped statutory source topics: '+law)
    for aid in items:
        plan = read(repo/'work'/aid/'case-plan.json')
        result = read(repo/'work'/aid/'result.json')
        if result.get('readiness_kind') == 'existing_evidence':
            validate_evidence(repo, aid, plan, no_capture=True)
            continue
        if not plan.get('comparisons'): raise ValueError('Full branch planning rejects empty comparisons: '+aid)
        if not {c['case_id'] for c in plan['cases']} <= all_cases: raise ValueError('Case missing from statutory branch matrix')
        manifest = read(repo/'work'/aid/'execution-manifest.json')
        for case in manifest['cases']:
            post = case.get('post_capture', {})
            if not post.get('command') or not post.get('feedback_command') or post.get('recorded_only') is not True:
                raise ValueError('Every exact case needs saved-only processing and feedback commands')
            if post.get('test_exit_code') != 0 or sha(within(repo/'work'/aid,post['test_log'])) != post.get('test_log_sha256'):
                raise ValueError('Saved-only processing needs a bound passing fixture test')
    review = read(repo/'work/_shared/branch-review.json')
    if review.get('coverage_sha256') != sha(repo/'work/_shared/branch-coverage.json') or review.get('missing_branches') != [] or not review.get('review_method'):
        raise ValueError('Independent full-law branch review missing or incomplete')
    if not review.get('candidate_review_method') or review.get('unreviewed_candidates') != []:
        raise ValueError('Independent candidate risk and comparison review missing')
    if blocked and require_ready: raise ValueError('Statutory capability blockers remain: '+','.join(blocked))
    return {'laws': len(laws), 'cases': len(all_cases), 'blocked_branches': blocked}
