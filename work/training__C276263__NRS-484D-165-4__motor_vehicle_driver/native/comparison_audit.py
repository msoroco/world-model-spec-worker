"""Independent parked-lamp comparison; reports observations, no legal verdict."""
import argparse
import json
from pathlib import Path

PREFIX='training__C276263__NRS-484D-165-4__motor_vehicle_driver__'

def audit(a,b):
    expected=(PREFIX+'probe_a',PREFIX+'probe_b')
    if (a.get('case_id'),b.get('case_id'))!=expected:
        raise ValueError('Exact case pair differs')
    if a.get('frames')!=600 or b.get('frames')!=600:
        raise ValueError('Complete parked windows required')
    if a.get('fixed_context')!=b.get('fixed_context'):
        raise ValueError('Road, vehicle or camera fixed context differs')
    context=a['fixed_context']
    if (context.get('curb_lane_id')!=-2 or context.get('duration_s')!=30 or
            context.get('rate_hz')!=20 or not context.get('ego_blueprint_id') or
            len(context.get('source_cameras',[]))!=4):
        raise ValueError('Fixed parked-lamp context incomplete')
    if (a.get('requested_beam_state'),b.get('requested_beam_state'))!=(
            'low_beam','high_beam'):
        raise ValueError('Declared beam difference missing')
    if (a.get('observed_beam_states'),b.get('observed_beam_states'))!=(
            ['low_beam'],['high_beam']):
        raise ValueError('Observed beam contrast missing')
    for result in (a,b):
        if (result.get('parked_activity_frames')!=600 or
                result.get('beam_pixel_reviewed_frames')!=600 or
                not result.get('source_sha256') or
                len(result.get('beam_aim_elevation_deg_range',[]))!=2 or
                len(result.get('relative_intensity_range',[]))!=2 or
                result.get('legal_verdict') is not None):
            raise ValueError('Source-backed parked beam observations incomplete')
    return {'format':'c276263-parked-headlamp-comparison-v1',
            'case_ids':list(expected),'fixed_context':context,
            'deliberate_difference':'observed low versus high beam state',
            'measured_aim_ranges':[a['beam_aim_elevation_deg_range'],
                                   b['beam_aim_elevation_deg_range']],
            'measured_intensity_ranges':[a['relative_intensity_range'],
                                         b['relative_intensity_range']],
            'original_native_observed':bool(a.get('original_native_observed') and
                                            b.get('original_native_observed')),
            'legal_verdict':None}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('probe_a');parser.add_argument('probe_b')
    args=parser.parse_args()
    print(json.dumps(audit(json.loads(Path(args.probe_a).read_text()),
                           json.loads(Path(args.probe_b).read_text())),indent=2))

if __name__=='__main__':main()
