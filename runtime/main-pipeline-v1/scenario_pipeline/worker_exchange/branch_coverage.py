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
        if (assignment_id(a,'testing') != aid or a.get('role') != 'testing' or
                a['law_id'] != original['law_id'] or not cell or
                a['actor'] not in cell['candidate_ego_parties'] or
                any(s in cell['allocated_sets'] for s in ('full-train','held-out'))):
            raise ValueError('Ineligible supplemental testing binding')
        if not binding.get('original_cell_incompatibility') or not binding.get('binding_reason'):
            raise ValueError('Changing cells requires original-cell incompatibility and binding review')
        result[aid] = {'input_sha256': sha(source), 'supplemental': True}
    return result


def assignment_path(repo, aid, item):
    return Path(repo)/('work' if item.get('supplemental') else 'inputs')/aid/'assignment.json'


def validate(repo, batch, items, require_ready=False):
    repo = Path(repo)
    matrix = read(repo/'work/_shared/branch-coverage.json')
    sources = read(repo/'inputs/coverage/branch-sources.json')['laws']
    if matrix.get('format') != 'worker-full-branch-coverage-v1' or matrix.get('batch_id') != batch['batch_id']:
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
    if blocked and require_ready: raise ValueError('Statutory capability blockers remain: '+','.join(blocked))
    return {'laws': len(laws), 'cases': len(all_cases), 'blocked_branches': blocked}
