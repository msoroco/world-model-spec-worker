"""Refresh selected construction sources after the paragraph (d) scope repair.

This updates sources and manifest hashes only. It deliberately leaves old proof
receipts stale until their CPU commands are rerun against the new bytes.
"""
import hashlib
import json
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
OLD_TO_NEW = {3: 2, 4: 3, 5: 4, 6: 5}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def refresh_construction(relative, plan_text, plan_sha, contract_text):
    path = PACKAGE / relative
    construction = json.loads(path.read_text())
    for item in construction['files']:
        name = item['path']
        if name == 'case-plan.json':
            item['content'] = plan_text
        elif name == 'measurement-contract.json':
            item['content'] = contract_text
        elif name == 'config.json':
            config = json.loads(item['content'])
            config['case_plan_sha256'] = plan_sha
            item['content'] = json.dumps(config, indent=2, ensure_ascii=False) + '\n'
        elif name.endswith('.py'):
            item['content'] = item['content'].replace(
                "root/'runtime/pipeline/scenario_pipeline'",
                "root/'runtime/scenario_pipeline'").replace(
                "root/'runtime/pipeline/python'",
                "root/'runtime/python'")
        materialized = path.parent / name
        if materialized.is_file() and materialized.resolve() != PACKAGE / 'case-plan.json':
            materialized.write_text(item['content'])
    write(path, construction)
    return sha(path)


def main():
    manifest_path = PACKAGE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    plan_path = PACKAGE / 'case-plan.json'
    plan_text = plan_path.read_text()
    plan_sha = sha(plan_path)
    for entry in manifest['cases']:
        contract_path = PACKAGE / entry['measurement_contract']
        contract = json.loads(contract_path.read_text())
        for row in contract['requirements']:
            row['disposition_index'] = OLD_TO_NEW.get(
                row['disposition_index'], row['disposition_index'])
        write(contract_path, contract)
        contract_text = contract_path.read_text()
        entry['construction_sha256'] = refresh_construction(
            entry['construction'], plan_text, plan_sha, contract_text)
        for candidate in entry.get('candidates', []):
            candidate['construction_sha256'] = refresh_construction(
                candidate['construction'], plan_text, plan_sha, contract_text)
    write(manifest_path, manifest)
    return len(manifest['cases'])


if __name__ == '__main__':
    print('Refreshed', main(), 'selected cases; receipts require CPU rerun')
