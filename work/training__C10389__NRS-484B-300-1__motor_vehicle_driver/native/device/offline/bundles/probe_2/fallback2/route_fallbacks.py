"""Compute eligibility of three distinct C10389 fallbacks from saved data."""
import argparse
import json
from pathlib import Path

from saved import measure


def route(bundle, saved):
    bundle = Path(bundle)
    cfg = json.loads((bundle / 'config.json').read_text())
    result = measure(bundle, saved)
    stopped = result['stopped_before_device_frames']
    crossed = result['front_body_at_device_station_frames']
    target_ambiguous = (cfg['route_policy'] == 'target' and
        (crossed == 0 or (stopped < 20 if result['requested_obey'] else stopped > 0)))
    visual_ambiguous = (result['reviewed_visible_device_face_frames'] == 0 or
                        result['reviewed_visible_approach_area_frames'] == 0)
    missing_authority = (not result['original_native_observed'] or
                         not result['authored_signal_is_official_placement'] or
                         not result['signal_specific_exception_reviewed'])
    return {'format': 'c10389-device-measured-routing-v1',
            'case_id': result['case_id'], 'candidate_id': result['candidate_id'],
            'source_kind': result['source_kind'],
            'triggers': {
                'fallback1': {'eligible': target_ambiguous,
                              'stopped_before_device_frames': stopped,
                              'front_body_at_device_station_frames': crossed,
                              'reason': 'target stop or passage not measured'},
                'fallback2': {'eligible': visual_ambiguous,
                              'reviewed_visible_device_face_frames':
                                  result['reviewed_visible_device_face_frames'],
                              'reviewed_visible_approach_area_frames':
                                  result['reviewed_visible_approach_area_frames'],
                              'reason': 'device face or approach-area pixels not reviewed'},
                'fallback3': {'eligible': missing_authority,
                              'original_native_observed':
                                  result['original_native_observed'],
                              'reason': 'original or official-placement and exception evidence absent'}},
            'selected_fallback': None, 'delivery_ready': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--saved', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(route(args.bundle, args.saved)))
