"""Generate per-case construction.json / config.json from the frozen scenario table.

Run from the repository root with Python 3.11:
  python3.11 work/<assignment>/tools/build_constructions.py
Shared implementation files are referenced by repo-relative `source`, so the
construction hash changes whenever any of them changes. No CARLA is imported.
"""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
import package_spec as P
import scenario as S

SHARED = ['runner.py', 'scenario.py', 'analyze.py', 'package_spec.py', 'tests/fixtures.py', 'tests/test_scenario.py', 'tests/test_runner_and_analysis.py']


def construction(variant, config):
    files = [{'path': 'config.json', 'content': json.dumps(config, indent=2) + '\n'}]
    for rel in SHARED:
        source = 'work/%s/%s' % (P.AID, rel)
        files.append({'path': rel, 'source': source, 'content': (REPO / source).read_text()})
    params = S.case_params(variant)
    return {'cell_id': P.CELL, 'actor': P.ACTOR, 'case_id': P.case_id(variant), 'law_id': P.LAW, 'status': 'draft',
            'entrypoint': 'runner.py', 'files': files,
            'mechanisms': ['Generated OpenDRIVE two-lane same-direction road with a parabolic hill crest',
                           'Speed-PI longitudinal control with a bumper-gap hold on the authored setpoint',
                           'Smoothstep lateral lane-change profile triggered by road position (not time)',
                           'Four synchronized RGB cameras written losslessly; PipelineCapture for original evidence'],
            'measurement_plan': {'channels': [c['name'] for c in config['case']['recording_description']['channels']],
                                 'finalizer': 'analyze.py', 'varied_from_base': S.changed_from_base(variant),
                                 'variable': S.VARIABLE_OF[variant]},
            'recording_description': config['case']['recording_description'],
            'static_checks': ['runner.py --check parses config, the case table and generated OpenDRIVE without CARLA',
                              'unit tests exercise scenario controllers and the saved-only finalizer on a synthetic fixture'],
            'termination_rules': ['Fixed %.0f s at %d Hz; no early termination' % (params['duration_s'], S.RATE_HZ),
                                  'Any exception writes native-run-status.json and leaves no sealed capture']}


def main():
    for index, variant in enumerate(P.CASES):
        config = P.config_for(variant)
        folder = HERE if index == 0 else HERE / 'cases' / variant
        folder.mkdir(parents=True, exist_ok=True)
        (folder / 'config.json').write_text(json.dumps(config, indent=2) + '\n')
        built = construction(variant, config)
        (folder / 'construction.json').write_text(json.dumps(built, indent=2) + '\n')
        print(P.case_id(variant), hashlib.sha256((folder / 'construction.json').read_bytes()).hexdigest()[:12])


if __name__ == '__main__':
    main()
