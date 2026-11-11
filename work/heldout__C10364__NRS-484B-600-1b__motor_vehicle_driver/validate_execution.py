"""Run pinned exact execution, physical and delivery acceptance gates."""

from pathlib import Path

from worker_exchange.execution_manifest import validate
from worker_exchange.delivery_handoff import validate_case


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def main():
    manifest = validate(REPO, ROOT.name)
    for case in manifest['cases']:
        validate_case(ROOT, case, ['held-out'])
    print(f'{len(manifest["cases"])} exact execution cases, per-case physical receipts '
          'and independent delivery acceptance bindings validate')


if __name__ == '__main__':
    main()
