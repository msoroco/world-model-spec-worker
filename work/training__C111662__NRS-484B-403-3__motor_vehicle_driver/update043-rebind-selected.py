"""Rebind selected U-turn constructions to the migrated frozen law input."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
AID = HERE.name


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def main():
    assignment_path = ROOT / 'inputs' / AID / 'assignment.json'
    current_sha = sha(assignment_path)
    assignment = read(assignment_path)
    if assignment['law']['id'] != assignment['law_id']:
        raise ValueError('Migrated canonical law identity differs')
    review_path = HERE / 'native/selection-review.json'
    review = read(review_path)
    for source in review['sources']:
        if source['path'] == f'inputs/{AID}/assignment.json':
            source['sha256'] = current_sha
    write(review_path, review)
    plan_path = HERE / 'case-plan.json'
    plan = read(plan_path)
    plan['selection_review']['sha256'] = sha(review_path)
    write(plan_path, plan)
    plan_sha = sha(plan_path)
    native_builder = HERE / 'native/build.py'
    code = native_builder.read_text()
    old_sha = next(line.split('"')[1] for line in code.splitlines()
                   if line.startswith('SOURCE_SHA = '))
    native_builder.write_text(code.replace(old_sha, current_sha))
    manifest_path = HERE / 'execution-manifest.json'
    manifest = read(manifest_path)
    if not (HERE / 'update043-pre-rebind-manifest.json').exists():
        (HERE / 'update043-pre-rebind-manifest.json').write_bytes(manifest_path.read_bytes())
    manifest['selection_review']['sha256'] = sha(review_path)
    manifest['status'] = 'selected_current_input_reproof_in_progress'
    for entry in manifest['cases']:
        suffix = entry['case_id'].removeprefix(AID + '__')
        for candidate in (entry, *entry['candidates']):
            name = candidate.get('id', 'primary')
            construction = read(HERE / candidate['construction'])
            for item in construction['files']:
                path = item['path']
                if path == 'inputs/' + AID + '/assignment.json' or path.endswith('assignment-source.json'):
                    item['content'] = assignment_path.read_text()
                elif path == 'case-plan.json' or path.endswith('/case-plan.json'):
                    item['content'] = plan_path.read_text()
                elif path == 'config.json' or path.endswith('/drafts/' + suffix + '/' + name + '/config.json'):
                    config = json.loads(item['content'])
                    config['assignment_sha256'] = current_sha
                    if 'case_plan_sha256' in config:
                        config['case_plan_sha256'] = plan_sha
                    item['content'] = json.dumps(config, indent=2) + '\n'
                elif path == 'work/' + AID + '/native/build.py':
                    item['content'] = native_builder.read_text()
                elif path.endswith('.py') and 'law_record' in item['content']:
                    item['content'] = item['content'].replace('law_record', 'law')
            target = HERE / 'native/package-selected-current-input' / suffix / name / 'construction.json'
            write(target, construction)
            candidate['construction'] = str(target.relative_to(HERE))
            candidate['construction_sha256'] = sha(target)
            candidate.pop('offline', None)
            candidate.pop('compatibility', None)
        for key in ('negative', 'post_capture', 'physical_preparation', 'delivery_acceptance'):
            if key in entry:
                entry['historical_' + key] = entry.pop(key)
        entry['preparation_status'] = 'current-input selected construction; exact CPU reproof pending'
    write(manifest_path, manifest)
    print(json.dumps({'assignment_sha256': current_sha, 'case_plan_sha256': plan_sha,
                      'selected_constructions': 16, 'manifest_sha256': sha(manifest_path)}))


if __name__ == '__main__':
    main()
