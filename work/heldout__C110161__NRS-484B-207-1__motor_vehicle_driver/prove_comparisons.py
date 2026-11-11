"""Run both independent comparisons on the exact bundled synthetic sources."""

from hashlib import sha256
import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
os.environ.setdefault('SCENARIO_PIPELINE_OUTPUT_ROOT',
                      str(ROOT / '.runtime-work/c110161-pipeline-output'))
sys.path.insert(0, str(ROOT / 'runtime/scenario_pipeline'))
from worker_exchange.fixture_recipe import materialize as make_fixture
from worker_exchange.runtime_cli import materialize as make_attempt
from worker_exchange.saved_processing import copy_sources
from overtake_comparison_audit import audit

PAIRS = (('left_pass_clearance', 'left_pass_wide', 'left_pass_narrow'),
         ('return_clearance_order', 'return_before_clear', 'return_after_clear'))


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def make_case(base, suffix):
    manifest = HERE / ('delivery-construction-manifest.json' if suffix == 'left_pass_wide'
                       else 'variant-construction-manifest.json')
    case = HERE.name + '__' + suffix
    entry = next(item for item in json.loads(manifest.read_text())['cases']
                 if item['case_id'] == case)
    recipe = ROOT / entry['fixture_recipe']
    fixture, attempt = base / (suffix + '-fixture'), base / (suffix + '-attempt')
    make_fixture(ROOT, recipe, fixture)
    make_attempt(manifest, case, attempt)
    copy_sources(fixture, attempt)
    return attempt, entry['construction_sha256']


def prove():
    with TemporaryDirectory(prefix='overtake-comparison-', dir=ROOT / '.runtime-work') as temp:
        base = Path(temp)
        for name, first, second in PAIRS:
            left, left_sha = make_case(base, first)
            right, right_sha = make_case(base, second)
            result = audit(name, left, right)
            if result['measured_values'][0] == result['measured_values'][1]:
                raise ValueError('Physical comparison did not vary the source measurement')
            rows = [json.loads(line) for line in (right / 'participant_footprints.jsonl').read_text().splitlines()]
            rows[0]['other_corners'][0][0] += 0.25
            (right / 'participant_footprints.jsonl').write_text(
                ''.join(json.dumps(row) + '\n' for row in rows))
            try:
                audit(name, left, right)
            except ValueError as error:
                if 'Fixed original roadway or overtaken participant changed' not in str(error):
                    raise
            else:
                raise ValueError('Changed overtaken participant was accepted')
            result.update(construction_sha256=[left_sha, right_sha],
                          negative_rejection='Fixed original roadway or overtaken participant changed',
                          fixture_only=True, actual_native_capture=False)
            output = HERE / ('comparison-' + name + '-proof.json')
            output.write_text(json.dumps(result, indent=2) + '\n')
            print(name, result['measured_values'], digest(output),
                  'synthetic_fixture_only')


if __name__ == '__main__':
    prove()
