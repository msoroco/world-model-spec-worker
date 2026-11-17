"""Create the canonical partial exact-case manifest from rebound constructions."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    draft = json.loads((ROOT / 'execution-manifest-draft-all.json').read_text())
    case_ids = {case['case_id'] for case in plan['cases']}
    if (len(case_ids) != 30 or
            {entry['case_id'] for entry in draft['cases']} != case_ids or
            any(item['status'] != 'selected_required' for item in
                plan['requirement_dispositions'])):
        raise ValueError('The full exact subsection has not been selected')
    for entry in draft['cases']:
        for candidate in [entry, *entry['candidates']]:
            if sha(ROOT / candidate['construction']) != candidate['construction_sha256']:
                raise ValueError('Changed exact construction')
    draft['status'] = 'selected_cpu_pending_proofs'
    draft['selected_branch'] = plan['selected_branch']
    draft['case_plan_sha256'] = sha(ROOT / 'case-plan.json')
    draft['selection_source_sha256'] = {
        'assignment': sha(REPO / 'inputs' / ROOT.name / 'assignment.json'),
        'witnesses': sha(REPO / 'inputs' / ROOT.name / 'witnesses.json')}
    draft['selection_kind'] = 'conditional_witness_full_subsection_cpu_plan'
    draft['original_native_observed'] = False
    draft['delivery_ready'] = False
    target = ROOT / 'execution-manifest.json'
    if target.exists():
        raise ValueError('Canonical manifest already exists; preserve bound proofs')
    target.write_text(json.dumps(draft, indent=2, ensure_ascii=False,
                                 allow_nan=False) + '\n')
    print(json.dumps({'cases': len(draft['cases']), 'candidates': 120,
                      'manifest': str(target.relative_to(REPO)),
                      'sha256': sha(target), 'delivery_ready': False}))


if __name__ == '__main__':
    main()
