"""Bind package-specific unit evidence and write precise partition handoffs."""
import hashlib
import json
from pathlib import Path
from build_partition import IDS, ROOT, SPECS


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


for aid in IDS:
    folder = ROOT / 'work' / aid
    result_path = folder / 'result.json'
    result = json.loads(result_path.read_text())
    assignment = json.loads((ROOT / 'inputs' / aid / 'assignment.json').read_text())
    law = assignment['law_id']
    spec = SPECS[law]
    unit_log = folder / 'tests/package-unit.log'
    assert 'OK\n' in unit_log.read_text()
    result['tests'].append({'command': 'PYTHONPATH=runtime/main-pipeline-v1/scenario_pipeline .venv-cpu/bin/python -m unittest discover -s '
                            + str((folder / 'tests').relative_to(ROOT)) + ' -p test_package.py -v',
                            'exit_code': 0, 'log': 'tests/package-unit.log', 'sha256': sha(unit_log)})
    result['reason'] = ('All exact cases pass pinned preflight, offline and full compatibility. '
                        + spec['gap'] + ' Physical measurements and legal judgment remain open.')
    result['unresolved_physical_checks'] = [spec['gap'],
        'Original CARLA route and full vehicle-body geometry',
        'Four-view source pixels, framing and full event duration',
        'Synthetic public-way or device authority status; no administrative confirmation']
    result_path.write_text(json.dumps(result, indent=2) + '\n')
    manifest = json.loads((folder / 'execution-manifest.json').read_text())
    cases = ', '.join(entry['case_id'].split('__')[-1] for entry in manifest['cases'])
    missing = {
        'NRS-484B-227-1': 'st.median_or_divider',
        'NRS-484B-220-1': 'st.one_way_roadway; dev.regulatory_sign',
        'NRS-484B-600-1a': 'env.ice_or_snow; env.visibility',
        'NRS-484B-413-2': 'sig.hand_signal',
    }.get(law, 'none identified for this exact capability package')
    text = f'''# {law} — partition 02 handoff

Status: **{result['status']}**; readiness kind: **capability**; physical acceptance: **false**.

## Exact experiment

Cases: {cases}. Comparison: {spec['difference']}. `execution-manifest.json` binds each materialized construction to its SHA-256 and each case to a package-specific compatibility receipt. `case-plan.json` maps every legal source observation term to an acquisition channel and original evidence source.

## CPU evidence

All {len(manifest['cases'])} exact cases passed pinned Core atom preflight, offline runner check, actual package analysis, native validation, mandatory-observation check, Lean adapter conversion, video render and final decode. The package unit suite passed. Logs are in `tests/`; compatibility receipts and analysis logs are in `compatibility/`. `fixture-diagnostic/` is a synthetic three-frame acquisition based only on this trial's shipped compatibility example; its straight-road geometry and video cannot establish law-specific motion or physical conditions.

## Open findings

Pinned adapter paths absent for indispensable legal observations: **{missing}**. {spec['gap']} A legal source term is retained in the plan and native channel even where the pinned Core adapter lacks its path. Required Core atoms use only supported `kin.position`, `kin.heading` and `kin.speed` paths.

The native experiment remains executable through `runner.py` and `analyze.py`, but no CARLA run, physical acceptance or compliance verdict was performed. Verify native OpenDRIVE connector topology, actor trajectories and full bodies, all four original camera views and recording duration, calibrated environmental conditions where applicable, and public-way or device authority with source evidence before physical or legal conclusions.
'''
    (folder / 'HANDOFF.md').write_text(text)
    print(aid, result['status'], len(manifest['cases']))
