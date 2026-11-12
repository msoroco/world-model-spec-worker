"""Check the pinned positive/negative handoff contract for every exact case."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent.parent
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
from worker_exchange.delivery_handoff import validate_case  # noqa: E402


def main():
    manifest = json.loads((ROOT / 'execution-manifest.json').read_text())
    selection = json.loads((REPO / 'inputs' / manifest['assignment_id'] /
                            'assignment.json').read_text())['selection_targets']
    for entry in manifest['cases']:
        receipt = validate_case(ROOT, entry, selection)
        if (receipt.get('diagnostic_only') is not True or
                receipt.get('physical_acceptance_claimed') is not False):
            raise ValueError('CPU delivery proof claims physical acceptance')
        print(entry['case_id'] + ': source-bound diagnostic contract validated')
    print('selected_cases=' + str(len(manifest['cases'])))


if __name__ == '__main__':
    main()
