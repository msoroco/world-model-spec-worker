"""Verify the current exact case contracts with the pinned CPU runtime."""
import json
from pathlib import Path

from scenario_pipeline.worker_exchange import delivery_handoff, execution_manifest


def main():
    repo = Path(__file__).resolve().parents[2]
    folder = Path(__file__).resolve().parent
    manifest = json.loads((folder / 'execution-manifest.json').read_text())
    for entry in manifest['cases']:
        delivery_handoff.validate_case(folder, entry, {'demo-test', 'full-test'})
        print('delivery', entry['case_id'], 'passed')
    execution_manifest.validate(repo, folder.name)
    print('execution manifest passed')


if __name__ == '__main__':
    main()
