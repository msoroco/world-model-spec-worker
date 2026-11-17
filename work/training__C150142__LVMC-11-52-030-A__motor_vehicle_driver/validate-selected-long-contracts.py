"""Check every long-case contract against its exact selected finalizer source."""
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path.insert(0, str(REPO / 'runtime/pipeline/scenario_pipeline'))
from worker_exchange.measurement_contract import validate


def main():
    manifest = json.loads((ROOT / 'execution-manifest.json').read_text())
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    count = 0
    for entry in manifest['cases']:
        slug = entry['case_id'].split('__')[-1]
        if not slug.startswith(('tour_bus_', 'shuttle_bus_', 'limo_', 'rtc_bus_')):
            continue
        construction = json.loads((ROOT / entry['construction']).read_text())
        analyzer = next(file['content'] for file in construction['files']
                        if file['path'] == entry['measurement_procedure']['entrypoint'])
        contract = json.loads((ROOT / 'selected-measurement-contracts' /
                               (slug + '.json')).read_text())
        validate(contract, plan['requirement_dispositions'], analyzer,
                 entry['case_id'])
        print(slug, 'valid')
        count += 1
    if count != 16:
        raise ValueError('Expected exactly sixteen selected long-case contracts')


if __name__ == '__main__':
    main()
