"""Exercise the far-case finalizer on a full synthetic original-source history.

Camera placeholders test finalizer source handling only. They are not footage,
compatibility evidence, saved-processing evidence, or physical acceptance.
"""
import argparse
import importlib.util
import json
import sys
from pathlib import Path

FOLDER = Path(__file__).resolve().parent
REPO = FOLDER.parents[1]
sys.path.insert(0, str(FOLDER))
sys.path.insert(0, str(FOLDER / 'cases/approaching_far'))
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
from prove_far_approach_history import make_sources, source_rows, write_jsonl
spec = importlib.util.spec_from_file_location('far_approach_draft_finalizer',
        FOLDER / 'cases/approaching_far/finalizer.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
finalize = module.finalize


CAMERAS = ('overview.mkv','approach.mkv','reference_corner.mkv','driver_reference.mkv')


def complete_sources(root, rows):
    make_sources(root, rows)
    write_jsonl(root / 'trace.jsonl',
                [{'frame': row['frame'], 'time_s': row['time_s'],
                  'position_m': [*row['ego']['position_xy_m'], 0],
                  'heading_deg': row['ego_heading_deg'],
                  'speed_mps': (row['ego']['velocity_xy_mps'][0]**2 +
                                row['ego']['velocity_xy_mps'][1]**2)**0.5}
                 for row in rows])
    (root / 'capture').mkdir()
    write_jsonl(root / 'capture/evidence.jsonl',
                [{'original_frame': row['frame'],
                  'recording_time_s': row['time_s'],
                  'fixture_only': True} for row in rows])
    for name in CAMERAS:
        (root / name).write_text('CPU finalizer test placeholder; no decoded video\n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root = args.output.resolve()
    if root.exists():
        raise ValueError('Use a fresh diagnostic output')
    root.mkdir(parents=True)
    rows = source_rows()
    positive = root / 'positive'
    complete_sources(positive, rows)
    analysis = finalize(positive, positive / 'analysis-report.json')
    result = json.loads((positive / 'result.json').read_text())
    observation = analysis['measurements']['far_approach_observation']['value']
    if observation['ego_turn_start_frame'] != 38074 or observation['opposing_entry_frame'] != 38149:
        raise ValueError('Finalizer lost the source-bound turn and entry ordering')
    if result['physical_checks']['setup']['status'] != 'met':
        raise ValueError('Full source history setup assessment did not pass')
    if result['physical_checks']['maneuver']['status'] != 'met':
        raise ValueError('Source-bound turn completion assessment did not pass')
    channels = sorted((positive / 'channels').glob('*.jsonl'))
    if len(channels) != 8 or any(sum(1 for _ in p.open()) != 900 for p in channels):
        raise ValueError('Finalizer did not rebuild all 900-sample observation channels')
    negative = root / 'missing_source_negative'
    complete_sources(negative, rows)
    (negative / 'interaction_history.jsonl').unlink()
    try:
        finalize(negative, negative / 'analysis-report.json')
    except ValueError as exc:
        if 'Missing required source: interaction_history.jsonl' not in str(exc):
            raise
    else:
        raise ValueError('Finalizer accepted missing original interaction history')
    print(json.dumps({'format': 'far-finalizer-cpu-proof',
                      'source_samples': 900, 'regenerated_channels': len(channels),
                      'channel_samples': 900,
                      'ego_turn_start_frame': observation['ego_turn_start_frame'],
                      'opposing_entry_frame': observation['opposing_entry_frame'],
                      'physical_setup_source_check': result['physical_checks']['setup']['status'],
                      'physical_maneuver_source_check': result['physical_checks']['maneuver']['status'],
                      'missing_source_negative_rejected': True,
                      'camera_media_validated': False,
                      'compatibility_proved': False,
                      'saved_processing_proved': False,
                      'physical_acceptance_claimed': False,
                      'legal_verdict_asserted': False}, indent=2))


if __name__ == '__main__':
    main()
