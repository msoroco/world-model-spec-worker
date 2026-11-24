"""Build separate current-runtime diagnostic sources for the remaining cases."""
import importlib.util
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('primary_builder', HERE / 'build-v2-primary.py')
builder = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = builder
spec.loader.exec_module(builder)


def build(suffix):
    builder.OUT = HERE / 'v2-primary' / suffix
    builder.SCRATCH = HERE.parents[1] / '.runtime-work/c111331-v2' / suffix
    builder.SCRATCH.mkdir(parents=True, exist_ok=True)
    reference = HERE.parents[1] / '.runtime-work/c111331-v2/witness_1'
    contrary = suffix in ('witness_2', 'exception_1_2')
    native = [json.loads(line) for line in (reference / 'c111331-native-samples.jsonl').read_text().splitlines()]
    for row in native:
        row['observed_pedestrian_signal']['state'] = 'dont_walk' if contrary else 'walk'
        row['requested_pedestrian_indication'] = 'dont_walk' if contrary else 'walk'
    builder.write_rows(builder.SCRATCH / 'c111331-native-samples.jsonl', native)
    (builder.SCRATCH / 'video_frames.jsonl').write_bytes((reference / 'video_frames.jsonl').read_bytes())
    builder.main(suffix)
    manifest = HERE / 'v2-primary-manifest.json'
    generated = json.loads(manifest.read_text())
    return generated['cases'][0]


def main():
    original_manifest = HERE / 'v2-primary-manifest.json'
    baseline = json.loads(original_manifest.read_text())
    cases = [baseline['cases'][0]]
    try:
        for suffix in ('witness_2', 'exception_1_1', 'exception_1_2'):
            cases.append(build(suffix))
    finally:
        original_manifest.write_text(json.dumps(baseline, indent=2) + '\n')
    baseline['cases'] = cases
    baseline['status'] = 'unselected_current_v2_cpu_four_case_proof'
    (HERE / 'v2-four-case-manifest.json').write_text(json.dumps(baseline, indent=2) + '\n')
    plan = json.loads((HERE / 'case-plan.json').read_text())
    (HERE / 'proposals/cases.json').write_text(json.dumps({'cases': plan['cases']}, indent=2) + '\n')
    print(json.dumps({'cases': [case['case_id'] for case in cases]}))


if __name__ == '__main__':
    main()
