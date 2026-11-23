"""Original-source software audit for one C178244 delivery attempt.

The diagnostic flag checks synthetic CPU capture only. Actual acceptance still
requires Native provenance, complete frames, physical motion, and pixel review.
"""
import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parents[1] / 'runtime/scenario_pipeline'))
from worker_exchange.media import audit as audit_video, check_four_view_sources

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError('Missing original source: ' + str(path))
    result = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    if not result:
        raise ValueError('Empty original source: ' + str(path))
    return result


def audit(attempt, case_id, diagnostic_fixture=False):
    attempt = Path(attempt)
    if not case_id.startswith(ROOT.name + '__'):
        raise ValueError('Wrong exact C178244 case')
    config = json.loads((attempt / 'config.json').read_text())
    result = json.loads((attempt / 'result.json').read_text())
    if (config.get('selected_case_id') != case_id or result.get('case_id') != case_id or
            config.get('cell_id') != 'C178244' or config.get('law_id') != 'NRS-484B-413-2'):
        raise ValueError('Exact case identity differs')
    if diagnostic_fixture:
        if result.get('provenance_kind') != 'synthetic_fixture' or result.get('diagnostic_fixture') is not True:
            raise ValueError('Diagnostic flag requires declared synthetic provenance')
    else:
        if result.get('provenance_kind') != 'native' or result.get('diagnostic_fixture') is True:
            raise ValueError('Native source provenance required')
        check = result.get('physical_checks', {}).get('maneuver', {})
        if not result.get('maneuver_completed') or check.get('status') != 'met':
            raise ValueError('Original physical completion proof required')
    mapping = rows(attempt / 'video_frames.jsonl')
    drive = rows(attempt / 'drive_history.jsonl')
    body = rows(attempt / 'body_history.jsonl')
    trace = rows(attempt / 'trace.jsonl')
    evidence = rows(attempt / 'capture/evidence.jsonl')
    count = len(mapping)
    if (any(len(source) != count for source in (drive, body, trace, evidence)) or
            (not diagnostic_fixture and count != config['rate_hz'] * config['duration_s'])):
        raise ValueError('Full original source frame coverage required')
    channels = {name: rows(attempt / 'channels' / (name + '.jsonl')) for name in
                ('ego_speed', 'ego_heading', 'ego_road_id', 'ego_turn_indicator')}
    if 'ego_position' in {x['name'] for x in config['recording_description']['channels']}:
        channels['ego_position'] = rows(attempt / 'channels/ego_position.jsonl')
    if any(len(channel) != count for channel in channels.values()):
        raise ValueError('Recorded channel history differs in length')
    previous = None
    for index, frame in enumerate(mapping):
        fid, time = frame.get('carla_frame'), frame.get('time_s')
        if (frame.get('video_frame') != index or type(fid) is not int or
                type(time) not in (int, float) or not math.isfinite(time)):
            raise ValueError('Original frame map invalid')
        if previous and (fid <= previous[0] or time <= previous[1]):
            raise ValueError('Original frame order invalid')
        previous = (fid, time)
        for source in (drive[index], body[index], trace[index]):
            if source.get('frame') != fid:
                raise ValueError('Original motion frame join invalid')
        if evidence[index].get('original_frame') != fid:
            raise ValueError('Original participant frame join invalid')
        for channel in channels.values():
            row = channel[index]
            if row.get('original_frame') != fid or abs(row.get('time_s', -math.inf) - time) > 1e-5:
                raise ValueError('Recorded channel time join invalid')
        source = drive[index]
        for name, key in [('ego_speed', 'ego_speed_mps'), ('ego_heading', 'ego_heading_deg'),
                          ('ego_road_id', 'native_road_id'), ('ego_position', 'ego_position_xy_m')]:
            if name in channels and channels[name][index]['value'] != source[key]:
                raise ValueError('Channel differs from retained drive source: ' + name)
        indicator = channels['ego_turn_indicator'][index]['value']
        if indicator.get('reported_mask') != source['ego_light_mask']:
            raise ValueError('Indicator readback differs from retained drive source')
    for name, digest in result.get('source_evidence_hashes', {}).items():
        if sha(attempt / name) != digest:
            raise ValueError('Sealed original source hash differs: ' + name)
    packet = json.loads((attempt / 'district-site-packet.json').read_text())
    route = json.loads((attempt / 'route_context.json').read_text())
    document = attempt / packet.get('source_document', '')
    if (not document.is_file() or sha(document) != packet.get('source_document_sha256') or
            route.get('district_source_sha256') != sha(document) or
            route.get('district_type') != packet.get('district_type') or
            packet.get('authored_map_sha256') != sha(attempt / 'road.xodr')):
        raise ValueError('District source, route and authored map do not join')
    if diagnostic_fixture:
        if not document.read_text().startswith('Synthetic site description'):
            raise ValueError('Diagnostic district packet is not identified as synthetic')
    elif (not packet.get('reviewer') or
          document.read_text().startswith('Synthetic site description')):
        raise ValueError('Independent original-site district review required')
    cameras = {name: attempt / (name + '.mkv') for name in CAMERAS}
    check_four_view_sources(cameras)
    decoded = {name: audit_video(path, count, mapping_sha256=sha(attempt / 'video_frames.jsonl'))['video_sha256']
               for name, path in cameras.items()}
    if not diagnostic_fixture:
        review = json.loads((attempt / 'pixel-review.json').read_text())
        if not review.get('reviewer') or review.get('reviewer', '').startswith('synthetic-'):
            raise ValueError('Independent original-camera pixel review required')
    return {'format': 'worker-c178244-independent-source-audit', 'case_id': case_id,
            'original_frames': count, 'frame_map_sha256': sha(attempt / 'video_frames.jsonl'),
            'sealed_result_sha256': sha(attempt / 'result.json'), 'decoded_cameras': decoded,
            'district_packet_sha256': sha(attempt / 'district-site-packet.json'),
            'software_audit_passed': True, 'diagnostic_fixture': diagnostic_fixture,
            'physical_acceptance_claimed': False, 'legal_conclusion': 'unresolved'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--case', required=True)
    parser.add_argument('--diagnostic-fixture', action='store_true')
    args = parser.parse_args()
    print(json.dumps(audit(args.attempt, args.case, args.diagnostic_fixture), indent=2))
