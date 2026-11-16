"""Build one exact, isolated conditions-permitting coverage point for CPU proof."""
from copy import deepcopy
import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SUFFIX = 'conditions_gap_120m'
CASE = HERE.name + '__' + SUFFIX


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, data):
    path.write_text(json.dumps(data, indent=2) + '\n')


def replace_once(value, old, new):
    if value.count(old) != 1:
        raise ValueError('Source template changed: ' + old[:60])
    return value.replace(old, new)


def main():
    # Separate source modules leave all existing selected constructions sealed.
    runner = (HERE/'runner.py').read_text()
    runner = replace_once(runner,
        'from truck_construction import spawn_exact_gap_pair\n',
        'from truck_construction import spawn_exact_gap_pair\n'
        'from qualitative_sweep_construction import spawn_sweep_pair\n')
    runner = replace_once(runner,
        "CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')\n",
        "CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')\n"
        "SWEEP_GAPS_M = {'conditions_gap_120m': 120.0}\n")
    runner = replace_once(runner,
        "suffix not in GAP_TARGETS_M and suffix not in WIDTH_CASES and suffix not in ('two_same_direction_lanes','overtaking')",
        "suffix not in GAP_TARGETS_M and suffix not in SWEEP_GAPS_M and suffix not in WIDTH_CASES and suffix not in ('two_same_direction_lanes','overtaking')")
    runner = replace_once(runner,
        "        if selected_case in GAP_TARGETS_M:\n            pair_context=spawn_exact_gap_pair(world,ego_bp,lead_bp,selected_case,transform_at)\n",
        "        if selected_case in SWEEP_GAPS_M:\n"
        "            pair_context=spawn_sweep_pair(world,ego_bp,lead_bp,SWEEP_GAPS_M[selected_case],transform_at)\n"
        "        elif selected_case in GAP_TARGETS_M:\n"
        "            pair_context=spawn_exact_gap_pair(world,ego_bp,lead_bp,selected_case,transform_at)\n")
    (HERE/'sweep_runner.py').write_text(runner)

    finalizer = (HERE/'finalizer.py').read_text()
    finalizer = replace_once(finalizer,
        "WIDTH_CASES = {'ego_width_below_80in': ('ego','below'),",
        "SWEEP_GAPS_M = {'conditions_gap_120m': 120.0}\n"
        "WIDTH_CASES = {'ego_width_below_80in': ('ego','below'),")
    finalizer = replace_once(finalizer,
        "if suffix not in GAP_TARGETS_M and suffix not in WIDTH_CASES and suffix not in ('two_same_direction_lanes','overtaking'):",
        "if suffix not in GAP_TARGETS_M and suffix not in SWEEP_GAPS_M and suffix not in WIDTH_CASES and suffix not in ('two_same_direction_lanes','overtaking'):")
    finalizer = replace_once(finalizer,
        "    if suffix in GAP_TARGETS_M:\n        target_check = {'target': 'minimum_sampled_body_gap_m',\n                        'requested': GAP_TARGETS_M[suffix], 'measured': minimum,",
        "    if suffix in GAP_TARGETS_M or suffix in SWEEP_GAPS_M:\n"
        "        requested = {**GAP_TARGETS_M, **SWEEP_GAPS_M}[suffix]\n"
        "        target_check = {'target': 'minimum_sampled_body_gap_m',\n"
        "                        'requested': requested, 'measured': minimum,")
    finalizer = replace_once(finalizer,
        "'matched': abs(minimum-GAP_TARGETS_M[suffix]) <= 2.0,",
        "'matched': abs(minimum-requested) <= 2.0,")
    (HERE/'sweep_finalizer.py').write_text(finalizer)

    generator = (HERE/'build_diagnostic.py').read_text()
    generator = replace_once(generator,
        "GAPS = {'gap_below_500ft':150.0,'gap_at_500ft':152.4,'gap_above_500ft':155.0}",
        "GAPS = {'gap_below_500ft':150.0,'gap_at_500ft':152.4,'gap_above_500ft':155.0,'conditions_gap_120m':120.0}")
    (HERE/'build_sweep_diagnostic.py').write_text(generator)

    base = json.loads((HERE/'construction.json').read_text())
    config = json.loads((HERE/'config.json').read_text())
    config['selected_case_id'] = CASE
    config['supported_case_ids'] = [CASE]
    config['physical_completion']['completion_goal_method'] += '; judgment sweep point is coverage only'
    base['case_id'] = CASE
    for entry in base['files']:
        if entry['path'] == 'runner.py':
            entry['content'] = runner
            entry['source'] = str((HERE/'sweep_runner.py').relative_to(ROOT))
        elif entry['path'] == 'finalizer.py':
            entry['content'] = finalizer
            entry['source'] = str((HERE/'sweep_finalizer.py').relative_to(ROOT))
        elif entry['path'] == 'config.json':
            entry['content'] = json.dumps(config, indent=2) + '\n'
            entry.pop('source', None)
        elif entry['path'] == 'tests/test_bundle.py':
            entry['content'] = (HERE/'sweep_bundle_test.py').read_text()
            entry['source'] = str((HERE/'sweep_bundle_test.py').relative_to(ROOT))
    base['files'].append({'path': 'qualitative_sweep_construction.py',
                          'content': (HERE/'qualitative_sweep_construction.py').read_text(),
                          'source': str((HERE/'qualitative_sweep_construction.py').relative_to(ROOT))})
    base['mechanisms'].append('Native-body-readback 120 m sweep setpoint on authored road')
    construction_path = HERE/'sweep-stage-construction.json'
    save(construction_path, base)
    manifest = {'format': 'worker-execution-manifest', 'assignment_id': HERE.name,
                'runtime_manifest_sha256': sha(ROOT/'runtime/SOURCE-MANIFEST.json'),
                'cases': [{'case_id': CASE, 'kind': 'delivery',
                           'construction': construction_path.name,
                           'construction_sha256': sha(construction_path),
                           'measurement_procedure': {'entrypoint': 'finalizer.py'},
                           'measurement_contract': 'measurement-contract.json',
                           'fixture_recipe': str((HERE/('fixture-recipe-'+SUFFIX+'.json')).relative_to(ROOT)),
                           'candidate_risk': {'status': 'physical',
                                              'reason': 'Native truck bodies or 45-second motion may miss the authored 120 m gap'},
                           'candidates': []}], 'status': 'staged_120m_cpu_proof_only'}
    variants_spec = importlib.util.spec_from_file_location('truck_camera_variants', HERE/'build_camera_fallbacks.py')
    variants = importlib.util.module_from_spec(variants_spec)
    variants_spec.loader.exec_module(variants)
    directory = HERE/'sweep-stage-fallbacks'
    directory.mkdir(exist_ok=True)
    for ident, old, new, metric_source, metric, failure, knobs in variants.VARIANTS:
        variant_runner = replace_once(runner, old, new)
        runner_path = directory/(ident+'-runner.py')
        runner_path.write_text(variant_runner)
        alternate = deepcopy(base)
        alternate['candidate_id'] = ident
        alternate['mechanisms'].append('alternative source-camera placement '+ident)
        for item in alternate['files']:
            if item['path'] == 'runner.py':
                item['content'] = variant_runner
                item['source'] = str(runner_path.relative_to(ROOT))
        construction_alt = directory/(ident+'-construction.json')
        save(construction_alt, alternate)
        manifest['cases'][0]['candidates'].append({
            'id': ident,
            'construction': str(construction_alt.relative_to(HERE)),
            'construction_sha256': sha(construction_alt),
            'trigger': {'source': metric_source, 'metric': metric,
                        'failure_condition': failure},
            'changed_knobs': knobs})
    save(HERE/'sweep-stage-manifest.json', manifest)
    print(json.dumps({'case_id': CASE, 'construction_sha256': sha(construction_path)}))


if __name__ == '__main__':
    main()
