"""Recompute every selected synthetic saved projection channel from raw actors."""
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CANDIDATES = ('primary', 'fallback1', 'fallback2', 'fallback3')
PARTS = ('vehicle', 'load', 'trailer')
FEET_PER_METER = 3.280839895013123


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def projection(actor, origin, normal):
    center = actor['center_xy_m']
    extent = actor['half_extent_xy_m']
    yaw = math.radians(actor['yaw_deg'])
    require(len(center) == len(extent) == 2
            and all(math.isfinite(v) for v in (*center, *extent, yaw))
            and min(extent) > 0, 'Invalid raw actor geometry')
    cosine, sine = math.cos(yaw), math.sin(yaw)
    return max(((center[0] + dx * cosine - dy * sine - origin[0]) * normal[0]
                + (center[1] + dx * sine + dy * cosine - origin[1]) * normal[1])
               for dx, dy in ((-extent[0], -extent[1]), (extent[0], -extent[1]),
                              (extent[0], extent[1]), (-extent[0], extent[1])))


def check(raw, frame_map, channel, curb, report, result):
    require(len(raw) == len(frame_map) == len(channel) == 600,
            'Full 600-frame source/channel interval missing')
    origin, normal = curb['origin_xy_m'], curb['street_normal_xy']
    require(len(origin) == len(normal) == 2
            and all(math.isfinite(v) for v in (*origin, *normal,))
            and abs(math.hypot(*normal) - 1.0) < 1e-9,
            'Reviewed curb normal is not unit length')
    computed = []
    actor_ids = None
    for i, (source, frame, output) in enumerate(zip(raw, frame_map, channel)):
        require(source.get('frame') == frame.get('video_frame') == i
                and source.get('native_frame') == frame.get('native_frame')
                and abs(source['time_s'] - frame['time_s']) < 1e-9
                and abs(output['time_s'] - frame['time_s']) < 1e-9,
                'Source/channel frame join differs: ' + str(i))
        require(source.get('source_kind') == 'synthetic_native_sample'
                and set(source['actors']) == set(PARTS),
                'Synthetic part inventory differs: ' + str(i))
        actors = source['actors']
        identities = {part: actors[part]['actor_id'] for part in PARTS}
        require(len(set(identities.values())) == 3
                and actors['load'].get('attached_to') == identities['vehicle']
                and actors['trailer'].get('attached_to') == identities['vehicle'],
                'Part identity or attachment differs: ' + str(i))
        if actor_ids is None:
            actor_ids = identities
        require(identities == actor_ids, 'Actor identity changed: ' + str(i))
        maximum = max(projection(actors[part], origin, normal) for part in PARTS)
        value = max(0.0, maximum) * FEET_PER_METER
        require(math.isfinite(output['value'])
                and abs(value - output['value']) < 1e-7,
                'Saved projection channel differs from raw actors: ' + str(i))
        computed.append(value)
    maximum = max(computed)
    measurements = report['measurements']
    require(abs(measurements['text_0_projection']['value'] - maximum) < 1e-7
            and abs(measurements['reviewed_scope_0_projection']['value']['vehicle_load_trailer_maximum_ft'] - maximum) < 1e-7
            and measurements['reviewed_scope_0_projection']['value']['frames'] == 600
            and abs(result['measured_values']['maximum_projection_perpendicular_to_curb_ft'] - maximum) < 1e-7,
            'Saved report/result maximum differs from source channel')
    require(report.get('physical_acceptance_claimed') is False
            and report.get('legal_verdict_claimed') is False
            and result.get('accepted') is False
            and result.get('legal_verdict_claimed') is False,
            'Diagnostic report claims acceptance')
    return maximum, actor_ids


def main():
    manifest_path = HERE / 'execution-manifest.json'
    manifest = read(manifest_path)
    receipts = []
    for case in manifest['cases']:
        suffix = case['case_id'].rsplit('__', 1)[-1]
        for candidate in CANDIDATES:
            selected = case if candidate == 'primary' else next(
                item for item in case['candidates'] if item['id'] == candidate)
            prefix = f'finalbound-chain-{suffix}-{candidate}'
            proof_path = HERE / (prefix + '-proof.json')
            saved_path = HERE / (prefix + '-saved.log')
            proof, saved = read(proof_path), read(saved_path)
            require(proof.get('cpu_chain_passed') is True
                    and proof.get('selected_manifest_sha256') == sha(manifest_path)
                    and saved.get('passed') is True
                    and saved.get('recorded_only') is True
                    and saved.get('case_id') == case['case_id']
                    and saved.get('candidate_id') == candidate
                    and saved['native_revision']['construction_sha256'] == selected['construction_sha256']
                    and sha(HERE / selected['construction']) == selected['construction_sha256'],
                    'Selected chain/manifest differs: ' + prefix)
            attempt = ROOT / '.runtime-work' / ('c229398-' + prefix + '-compatibility')
            analysis = Path(saved['analysis_directory'])
            require(analysis.is_dir() and attempt.is_dir(), 'Selected saved sources absent: ' + prefix)
            source_names = ('native-raw-actors.jsonl', 'video_frames.jsonl',
                            'reviewed-curb.json', 'native-curb-proposal.json')
            for name in source_names:
                require(sha(attempt / name) == saved['original_source_hashes'][name],
                        'Original source hash differs: ' + prefix + '/' + name)
            curb = read(attempt / 'reviewed-curb.json')
            require(curb.get('source_kind') == 'synthetic_native_sample'
                    and curb.get('source_file') == 'native-curb-proposal.json'
                    and curb.get('source_sha256') == sha(attempt / curb['source_file']),
                    'Curb source binding differs: ' + prefix)
            report_path = analysis / 'analysis-report.json'
            result_path = analysis / 'result.json'
            channel_path = analysis / 'channels/maximum_projection_perpendicular_to_curb.jsonl'
            report, result = read(report_path), read(result_path)
            require(report.get('case_id') == result.get('case_id') == case['case_id']
                    and saved.get('result_sha256') == sha(result_path),
                    'Saved report/result identity differs: ' + prefix)
            expected_sources = {name: sha(attempt / name) for name in
                                ('native-raw-actors.jsonl', 'reviewed-curb.json', 'native-curb-proposal.json')}
            require(report['measurements']['text_0_projection']['sources'] == expected_sources
                    and report['measurements']['reviewed_scope_0_projection']['sources'] == expected_sources,
                    'Saved measurement source hashes differ: ' + prefix)
            raw, frames, channel = rows(attempt / 'native-raw-actors.jsonl'), rows(attempt / 'video_frames.jsonl'), rows(channel_path)
            maximum, actor_ids = check(raw, frames, channel, curb, report, result)
            altered = json.loads(json.dumps(channel))
            altered[-1]['value'] += 0.01
            try:
                check(raw, frames, altered, curb, report, result)
            except ValueError as error:
                require(str(error).endswith('599'), 'Unexpected channel negative failure')
            else:
                raise ValueError('Corrupted final channel frame accepted')
            altered = json.loads(json.dumps(raw))
            altered[-1]['actors']['load']['attached_to'] = 'unrelated'
            try:
                check(altered, frames, channel, curb, report, result)
            except ValueError as error:
                require(str(error).endswith('599'), 'Unexpected attachment negative failure')
            else:
                raise ValueError('Corrupted final attachment accepted')
            receipts.append({'case_id': case['case_id'], 'candidate': candidate,
                             'chain_proof_sha256': sha(proof_path),
                             'saved_receipt_sha256': sha(saved_path),
                             'raw_actor_sha256': sha(attempt / 'native-raw-actors.jsonl'),
                             'channel_sha256': sha(channel_path),
                             'analysis_report_sha256': sha(report_path),
                             'maximum_projection_ft': maximum, 'frames': 600,
                             'actor_ids': actor_ids, 'negative_controls_rejected': 2})
    receipt = {'format': 'c229398-saved-projection-channel-audit-v1',
               'passed': True, 'diagnostic_only': True,
               'source_kind': 'synthetic_native_sample',
               'selected_manifest_sha256': sha(manifest_path),
               'selected_candidate_count': len(receipts),
               'negative_controls_rejected': 2 * len(receipts),
               'original_native_verified': False,
               'physical_acceptance_claimed': False,
               'legal_verdict': None, 'candidates': receipts}
    destination = HERE / 'saved-projection-channel-audit.json'
    destination.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'passed': True, 'selected_candidates': len(receipts),
                      'negative_controls_rejected': 2 * len(receipts)}))


if __name__ == '__main__':
    main()
