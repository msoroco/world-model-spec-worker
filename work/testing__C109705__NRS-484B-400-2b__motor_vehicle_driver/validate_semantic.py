"""Run the current runtime semantic gate for this exact selected package."""
import json
from pathlib import Path

from scenario_pipeline.worker_exchange.semantic_delivery import validate

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def main():
    original = json.loads((REPO / 'inputs' / HERE.name / 'assignment.json').read_text())
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    print(json.dumps(validate(HERE, original, manifest), sort_keys=True))


if __name__ == '__main__':
    main()
