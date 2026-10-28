"""Refresh only existing cited file hashes after merging the frozen update 005 input."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main():
    changed = []
    for plan_path in sorted((ROOT / 'work').glob('testing*/case-plan.json')):
        plan = json.loads(plan_path.read_text())
        for source in plan['sources']:
            path = ROOT / source['path']
            if not path.is_file():
                raise FileNotFoundError(path)
            current = hashlib.sha256(path.read_bytes()).hexdigest()
            if source['sha256'] != current:
                changed.append({'assignment_id': plan['assignment_id'],
                                'path': source['path'], 'old_sha256': source['sha256'],
                                'new_sha256': current})
                source['sha256'] = current
        if any(item['assignment_id'] == plan['assignment_id'] for item in changed):
            plan_path.write_text(json.dumps(plan, indent=2) + '\n')
    report = ROOT / 'work/_shared/source-refresh005.json'
    report.write_text(json.dumps({'format': 'update005-cited-source-refresh-v1',
                                  'changes': changed}, indent=2) + '\n')
    print(json.dumps({'changed_citations': len(changed), 'report': str(report.relative_to(ROOT))}))


if __name__ == '__main__':
    main()
