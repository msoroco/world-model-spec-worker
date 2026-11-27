"""Source-bound two-case comparison and changed-trajectory negative."""
import json
import os
import sys
import tempfile
from pathlib import Path


def main():
    repo = Path(__file__).resolve().parents[3]
    folder = Path(__file__).resolve().parents[1]
    scratch = repo / '.runtime-work'
    output_root = Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT']).resolve()
    if scratch not in output_root.parents:
        raise ValueError('Runtime output must stay under .runtime-work')
    sys.path.insert(0, str(repo / 'runtime/scenario_pipeline'))
    sys.path.insert(0, str(folder / 'native'))
    from worker_exchange.fixture_recipe import materialize
    from audit_comparison import audit
    from measure_readiness import measure
    from scene import CASES

    with tempfile.TemporaryDirectory(dir=scratch, prefix='c405647-comparison-') as temporary:
        work = Path(temporary)
        roots = {}
        reports = {}
        for condition in CASES:
            root = work / condition
            materialize(repo, folder / 'selected-fixtures' / condition / 'fixture-recipe.json', root)
            roots[condition] = root
            reports[condition] = work / (condition + '-observation.json')
            reports[condition].write_text(json.dumps(measure(root), indent=2) + '\n')
        positive = audit(roots, reports)
        if positive['physical_acceptance_claimed'] or positive['legal_verdict_claimed']:
            raise ValueError('Comparison claimed physical or legal acceptance')
        print('positive: fixed trigger context, source hashes and brake-response difference passed')

        changed = roots[CASES[1]] / 'approach_trace.jsonl'
        rows = [json.loads(line) for line in changed.read_text().splitlines()]
        rows[100]['emergency_speed_mps'] += 0.5
        changed.write_text(''.join(json.dumps(row, separators=(',', ':')) + '\n' for row in rows))
        reports[CASES[1]].write_text(json.dumps(measure(roots[CASES[1]]), indent=2) + '\n')
        try:
            audit(roots, reports)
        except ValueError as error:
            if 'Comparison changed emergency trajectory or indication' not in str(error):
                raise
        else:
            raise ValueError('Changed emergency trajectory was accepted')
        print('negative: changed emergency trajectory rejected')


if __name__ == '__main__':
    main()
