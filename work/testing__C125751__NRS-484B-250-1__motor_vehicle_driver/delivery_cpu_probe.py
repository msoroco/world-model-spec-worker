"""Exercise original-media/Core joins on a synthetic case; reject Native delivery."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

from delivery_audit import verify_core, verify_media, verify_sources


def run(case: str, attempt: Path, output: Path) -> dict:
    root = Path(__file__).resolve().parents[2]
    pipeline_output = Path(os.environ.get('SCENARIO_PIPELINE_OUTPUT_ROOT', '')).resolve()
    if root / '.runtime-work' not in pipeline_output.parents:
        raise ValueError('Set SCENARIO_PIPELINE_OUTPUT_ROOT below .runtime-work first')
    sys.path.insert(0, str(root / 'runtime/scenario_pipeline'))
    from worker_exchange import media
    attempt = attempt.resolve()
    output = output.resolve()
    if root / '.runtime-work' not in output.parents or output.exists():
        raise ValueError('Use a fresh diagnostic output below .runtime-work')
    output.mkdir(parents=True)
    provenance = json.loads((attempt / 'acquisition-provenance.json').read_text())
    if provenance.get('provenance_kind') != 'synthetic_fixture' or provenance.get('diagnostic_fixture') is not True:
        raise ValueError('CPU delivery probe requires an explicitly synthetic source')
    result = json.loads((attempt / 'result.json').read_text())
    if result.get('case_id') != case or not result.get('realized_observables'):
        raise ValueError('Selected saved result or measured observables missing')
    mapping = [json.loads(line) for line in (attempt / 'video_frames.jsonl').read_text().splitlines()]
    source = {'frames': mapping}
    decode = media.audit(attempt / 'raw.mkv', len(mapping),
                         mapping_sha256=media.sha(attempt / 'video_frames.jsonl'),
                         receipt=output / 'primary-decode.json')
    verify_media(attempt, source, decode, Path(media.__file__))
    verify_core(attempt, source)
    try:
        verify_sources(case, attempt)
    except ValueError as error:
        if 'original Native lifecycle unverified' not in str(error):
            raise
    else:
        raise ValueError('Synthetic source passed original Native gate')
    return {'case_id': case, 'diagnostic_fixture': True,
            'primary_full_decode_frames': decode['frames'],
            'core_original_frame_join': True,
            'saved_result_has_measured_observables': True,
            'production_native_source_rejected': True,
            'physical_acceptance_claimed': False,
            'statutory_applicability_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--attempt', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(run(args.case, args.attempt, args.output), indent=2))
