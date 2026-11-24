"""Independently audit fixed sources and declared differences for both pairs."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / '.runtime-work'
PAIRS = (('witness_1', 'witness_2'), ('exception_1_1', 'exception_1_2'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(value):
    return [json.loads(line) for line in value.splitlines() if line.strip()]


def main():
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    plan = json.loads((HERE / 'case-plan.json').read_text())
    if len(plan['comparisons']) != 2 or len(manifest['cases']) != 4:
        raise ValueError('Two controlled comparisons across four exact cases required')
    records = []
    for pair, comparison in zip(PAIRS, plan['comparisons']):
        if comparison['case_ids'] != [HERE.name + '__' + suffix for suffix in pair]:
            raise ValueError('Comparison case identity differs')
        specs = [json.loads((HERE / ('current-' + suffix + '-diagnostic.json')).read_text()) for suffix in pair]
        left, right = specs
        fixed_files = ('trace.jsonl', 'capture/evidence.jsonl', 'capture/native/frames.jsonl',
                       'video_frames.jsonl', 'capture/manifest.json')
        for name in fixed_files:
            if left['files'][name] != right['files'][name]:
                raise ValueError('Fixed motion or frame mapping differs: ' + name)
        if left['graphs'] != right['graphs'] or left['videos'] != right['videos']:
            raise ValueError('Fixed graph or four cameras differ')
        context_name = 'steady-context.json' if pair[0].startswith('witness') else 'exception-context.json'
        contexts = [json.loads(spec['files'][context_name]) for spec in specs]
        varying_context = {'steady_start_s'} if pair[0].startswith('witness') else {'exception_source_comparison'}
        for name in set(contexts[0]) | set(contexts[1]):
            if name not in varying_context and contexts[0].get(name) != contexts[1].get(name):
                raise ValueError('Fixed crossing context differs: ' + name)
        source_name = 'steady-samples.jsonl' if pair[0].startswith('witness') else 'exception-samples.jsonl'
        samples = [rows(spec['files'][source_name]) for spec in specs]
        if any(len(items) != 600 for items in samples):
            raise ValueError('Full 600-frame comparison source missing')
        fixed_sample = ('native_frame', 'time_s', 'crosswalk_id', 'device_id',
                        'pedestrian_xy_m', 'pedestrian_footprint_xy_m')
        for item in zip(*samples):
            if any(item[0].get(name) != item[1].get(name) for name in fixed_sample):
                raise ValueError('Fixed pedestrian motion differs')
        measured = []
        for suffix in pair:
            attempt = SCRATCH / ('c10316-d4-compat-witness1-primary-v8' if suffix == 'witness_1'
                                 else 'c10316-d4-compat-' + suffix + '-primary')
            saved = SCRATCH / ('c10316-d4-saved-witness1-primary' if suffix == 'witness_1'
                               else 'c10316-d4-saved-' + suffix + '-primary') / 'v0001/processing.json'
            report = json.loads((attempt / 'analysis-report.json').read_text())
            key = 'steady_entry_and_progress' if suffix.startswith('witness') else 'prior_entry_exception_source_facts'
            value = report['measurements'][key]['value']
            processing = json.loads(saved.read_text())
            if not processing['passed'] or not processing['recorded_only'] or value['original_frames'] != 600:
                raise ValueError('Saved comparison source or full duration differs')
            measured.append(value['entry_relative_to_steady'] if suffix.startswith('witness') else value['entry_indication'])
        expected = ['before_steady', 'at_or_after_steady'] if pair[0].startswith('witness') else ['dont_walk_flashing', 'walk']
        if measured != expected:
            raise ValueError('Declared comparison difference not measured')
        records.append({'comparison_id': comparison['comparison_id'],
                        'case_ids': comparison['case_ids'],
                        'fixed_motion_graph_camera_context': True,
                        'source_sha256': [sha(HERE / ('current-' + suffix + '-diagnostic.json')) for suffix in pair],
                        'measured_difference': measured,
                        'physical_or_legal_acceptance_claimed': False})
    receipt = {'format': 'c10316-d4-selected-comparison-audit', 'passed': True,
               'manifest_sha256': sha(HERE / 'execution-manifest.json'),
               'comparisons': records}
    output = HERE / 'current-public/comparison-audit.json'
    output.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'comparisons': len(records), 'sha256': sha(output)}))


if __name__ == '__main__':
    main()
