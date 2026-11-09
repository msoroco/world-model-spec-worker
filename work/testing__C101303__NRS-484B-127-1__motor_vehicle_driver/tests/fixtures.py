"""Synthetic, textual attempt trees for CPU tests. Provenance is a software fixture."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import package_spec as P
import scenario as S


def build(root, variant='base', wet=None):
    root = Path(root)
    (root / 'channels').mkdir(parents=True)
    (root / 'capture').mkdir()
    config = P.config_for(variant)
    (root / 'config.json').write_text(json.dumps(config))
    params = S.case_params(variant)
    rows = S.preview(variant)
    samples, trace, frames, evidence = [], [], [], []
    for r in rows:
        def body(s, t):
            return [[s + dx, -t + dy, 0.0] for dx in (-2.35, 2.35) for dy in (-1.0, 1.0)]
        samples.append({'frame': r['frame'], 'time_s': r['time_s'], 'ego_lane_id': r['ego_lane_id'], 'ego_road_id': 1, 'ego_s_m': r['ego_s_m'],
                        'ego_body_vertices_m': body(r['ego_s_m'], r['ego_t_m']), 'ego_speed_mps': r['ego_speed_mps'], 'lead_lane_id': r['lead_lane_id'],
                        'lead_s_m': r['lead_s_m'], 'lead_body_vertices_m': body(r['lead_s_m'], r['lead_t_m']), 'lead_speed_mps': r['lead_speed_mps'],
                        'lead_in_ego_lane': r['bumper_gap_m'] is not None, 'bumper_gap_m': r['bumper_gap_m'],
                        'queued_speed_mps': params['lead_speed_mps'] if r['queued_s_m'] else None, 'queued_s_m': r['queued_s_m'],
                        'ego_pitch_deg': 0.0, 'ego_elevation_m': S.elevation_m(r['ego_s_m'])})
        trace.append({'frame': r['frame'], 'time_s': r['time_s'], 'position': {'x': r['ego_s_m'], 'y': -r['ego_t_m'], 'z': 0.0},
                      'heading_deg': 0.0, 'speed_mps': r['ego_speed_mps']})
        frames.append({'video_frame': len(frames), 'carla_frame': r['frame'], 'native_frame': r['frame'], 'time_s': r['time_s']})
        evidence.append({'world': {'weather': {'wetness': params['wetness'] if wet is None else wet}}})
    for name, data in (('following_samples.jsonl', samples), ('trace.jsonl', trace), ('video_frames.jsonl', frames), ('capture/evidence.jsonl', evidence)):
        (root / name).write_text(''.join(json.dumps(x) + '\n' for x in data))
    for name, key in (('ego_speed_mps', 'ego_speed_mps'), ('lead_speed_mps', 'lead_speed_mps'), ('bumper_gap_m', 'bumper_gap_m'), ('ego_lane_id', 'ego_lane_id')):
        (root / 'channels' / (name + '.jsonl')).write_text(''.join(json.dumps({'time_s': r['time_s'], 'value': -1.0 if r[key] is None else r[key]}) + '\n' for r in rows))
    context = {'case_parameters': params, 'public_way_road_ids': [1], 'crest_s_m': S.CREST_S_M, 'crest_vertical_curve_m': S.CREST_VERTICAL_CURVE_M,
               'grade': S.GRADE, 'lane_width_m': S.LANE_WIDTH_M, 'road_length_m': S.ROAD_LENGTH_M,
               'surface': {'wetness': params['wetness'], 'precipitation': params['precipitation'], 'tire_friction': params['tire_friction'], 'ice_or_snow': False},
               'vehicle_length_m': S.VEHICLE_LENGTH_M, 'lane_change_trigger_s_m': S.LANE_CHANGE_TRIGGER_S_M}
    (root / 'surface_context.json').write_text(json.dumps(context))
    (root / 'acquisition-provenance.json').write_text(json.dumps({'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True}))
    return config
