"""Independently compare saved diagnostic edge trajectories with fixed context."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def main():
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    entries = {e['case_id'].rsplit('__', 1)[-1]: e for e in manifest['cases']}
    if set(entries) != {'reference', 'contrast'}:
        raise ValueError('Exact comparison pair missing')
    samples = {}
    outputs = {}
    for suffix, entry in entries.items():
        source = HERE / 'current-fixture' / suffix / 'actor-frames.jsonl'
        samples[suffix] = rows(source)
        receipt = json.loads((HERE / 'current-public' /
                              (suffix + '-primary-compatibility.json')).read_text())
        saved = json.loads((HERE / 'current-public' /
                            (suffix + '-primary-processing.json')).read_text())
        if (not receipt['passed'] or not saved['passed'] or
                receipt['construction_sha256'] != entry['construction_sha256'] or
                saved['analysis_revision']['construction_sha256'] != entry['construction_sha256'] or
                saved['original_source_hashes']['actor-frames.jsonl'] != sha(source)):
            raise ValueError('Saved exact construction or source changed: ' + suffix)
        outputs[suffix] = {'case_id': entry['case_id'],
                           'construction_sha256': entry['construction_sha256'],
                           'actor_frames_sha256': sha(source),
                           'compatibility_sha256': sha(HERE / 'current-public' /
                               (suffix + '-primary-compatibility.json')),
                           'processing_sha256': sha(HERE / 'current-public' /
                               (suffix + '-primary-processing.json'))}
    reference, contrast = samples['reference'], samples['contrast']
    if len(reference) != 600 or len(contrast) != 600:
        raise ValueError('Full diagnostic comparison has fewer than 600 frames')
    for i, (a, b) in enumerate(zip(reference, contrast)):
        if (a['frame'] != b['frame'] or a['native_frame'] != b['native_frame'] or
                a['time_s'] != b['time_s'] or a['approach'] != b['approach']):
            raise ValueError('Fixed approach/frame context changed at frame ' + str(i))
    reference_y = reference[-1]['subject']['center_xy_m'][1]
    contrast_y = contrast[-1]['subject']['center_xy_m'][1]
    if not reference_y < contrast_y - 2:
        raise ValueError('Requested right-edge movement does not separate the pair')
    result = {'format': 'c405647-current-comparison-audit',
              'case_ids': [entries[s]['case_id'] for s in ('reference', 'contrast')],
              'frames_per_case': 600, 'fixed_approach_and_frame_join': True,
              'comparison_variable': 'right_edge_clear_intersection_position',
              'final_subject_y_m': {'reference': reference_y, 'contrast': contrast_y},
              'sources': outputs, 'diagnostic_only': True,
              'original_native_observed': False, 'physical_acceptance': False,
              'legal_verdict': None}
    path = HERE / 'current-public' / 'comparison-audit.json'
    path.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'passed': True, 'comparison_sha256': sha(path),
                      'frames_per_case': 600}))


if __name__ == '__main__':
    main()
