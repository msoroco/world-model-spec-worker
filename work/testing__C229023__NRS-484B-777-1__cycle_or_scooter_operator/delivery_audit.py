"""Independent original-source audit for right-side cycle pass delivery."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

from analysis import original
from comparison_audit import value
from rightside import need


VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def decode_camera(video, frame_map_sha):
    repo = Path(__file__).resolve().parents[2]
    scratch = repo / '.runtime-work'
    output = Path(os.environ.get('SCENARIO_PIPELINE_OUTPUT_ROOT',
                                 scratch / 'c229023-7771-owner-nov26' / 'audit-output')).resolve()
    need(scratch in output.parents, 'pipeline output must remain under .runtime-work')
    os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(output)
    os.environ['TMPDIR'] = str(scratch.resolve())
    sys.path.insert(0, str(repo / 'runtime/scenario_pipeline'))
    from worker_exchange.media import audit as decode
    return decode(video, 900, mapping_sha256=frame_map_sha)


def audit_delivery(attempt, report_path):
    attempt = Path(attempt).resolve()
    expected, _ = original(attempt)
    report_path = Path(report_path).resolve()
    report = json.loads(report_path.read_text())
    need(report == expected, 'saved original right-side analysis differs from source readback')
    measured = value(report)
    need(measured['frame_count'] == 900 and
         measured['initial_relative_station_m'] < 0 and
         measured['terminal_relative_station_m'] > 0,
         'original behind/alongside/ahead pass incomplete')
    need(measured['minimum_surface_clearance_m'] >= 0 and
         measured['minimum_right_edge_distance_m'] >= 0,
         'original cycle body overlaps right boundary or other participant')
    frame_map_sha = sha(attempt / 'video_frames.jsonl')
    decodes = {name: decode_camera(attempt / (name + '.mkv'), frame_map_sha)
               for name in VIEWS}
    need(all(item['frames'] == 900 and item.get('rgb_sequence_sha256')
             for item in decodes.values()),
         'complete original camera pixel decode missing')
    return {'format': 'worker-right-side-delivery-source-audit',
            'case_id': report['case_id'],
            'attempt_sources_sha256': sha(attempt / 'original-sources.json'),
            'analysis_report_sha256': sha(report_path),
            'original_frame_count': 900, 'source_decodes': decodes,
            'physical_acceptance_claimed': False, 'legal_verdict_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--case-id', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    need(not args.output.exists(), 'retain prior delivery audit')
    result = audit_delivery(args.attempt, args.report)
    need(result['case_id'] == args.case_id, 'audit selected exact case differs')
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
