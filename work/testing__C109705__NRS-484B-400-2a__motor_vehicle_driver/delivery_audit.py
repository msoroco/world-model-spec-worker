"""Independent, source-bound CPU audit for one retained 400(2)(a) attempt.

A diagnostic fixture can exercise every check but is never delivery accepted.
The real acceptance path additionally requires a reviewed public-highway source.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

from saved_delivery import PREFIX, SUFFIXES, audit_original_pixels


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def _source(attempt, acquisition, name):
    path = attempt / name
    declared = acquisition.get(name, {})
    if (not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(attempt.resolve())
            or declared.get('kind') != 'original_native' or _sha(path) != declared.get('sha256')):
        raise ValueError('Missing or stale original source: ' + name)
    return path


def audit(attempt, case_id, *, allow_diagnostic=False):
    attempt = Path(attempt)
    if case_id not in {PREFIX + suffix for suffix in SUFFIXES}:
        raise ValueError('wrong exact delivery case')
    acquisition = json.loads((attempt / 'acquisition.json').read_text())
    if acquisition.get('case_id') != case_id:
        raise ValueError('original acquisition case mismatch')
    diagnostic = acquisition.get('diagnostic_fixture') is True
    if diagnostic and not allow_diagnostic:
        raise ValueError('diagnostic source cannot be delivery accepted')
    pixels = audit_original_pixels(attempt, case_id, allow_diagnostic=allow_diagnostic)
    history = _rows(_source(attempt, acquisition, 'approach-history.jsonl'))
    body = _rows(_source(attempt, acquisition, 'body_history.jsonl'))
    frame_map = _rows(_source(attempt, acquisition, 'video_frames.jsonl'))
    if len(history) != 900 or len(body) != 900 or len(frame_map) != 900:
        raise ValueError('original physical and media frame coverage differs')
    for index, (a, b, f) in enumerate(zip(history, body, frame_map)):
        if (a['frame'] != b['frame'] or a['frame'] != f['frame'] or f['video_frame'] != index
                or abs(a['time_s'] - b['time_s']) > 1e-4
                or abs(a['time_s'] - f['time_s']) > 1e-4
                or a['road_id'] != b['road_id']
                or a['ego_body_vertices_xy_m'] != [v[:2] for v in b['body_vertices_m']]):
            raise ValueError('physical body and original video source join differs')
    from scenario_pipeline.worker_exchange.native_output import assess_left_turn
    physical = assess_left_turn(attempt)
    if physical['status'] != 'met' or not physical.get('observed') or not physical.get('sources'):
        raise ValueError('original physical completion not established: ' + physical['status'])
    inventory = _rows(_source(attempt, acquisition, 'graph-frames.jsonl'))
    if len(inventory) != 900:
        raise ValueError('all-participant graph coverage incomplete')
    actor_id = None
    for position, (row, frame) in enumerate(zip(inventory, frame_map)):
        graph_ref = row.get('adapter_graph')
        if not isinstance(graph_ref, str) or Path(graph_ref).is_absolute():
            raise ValueError('original graph source path invalid')
        graph_path = (attempt / graph_ref).resolve()
        if (not graph_path.is_relative_to(attempt.resolve()) or not graph_path.is_file()
                or graph_path.is_symlink() or _sha(graph_path) != row.get('sha256')):
            raise ValueError('original graph source changed')
        graph = json.loads(graph_path.read_text())
        meta = graph.get('metadata', {})
        if (row.get('frame') != frame['frame'] or graph.get('format') != 'native-adapter-graph-v1'
                or meta.get('frame') != frame['frame'] or
                type(meta.get('simulation_time_s')) not in (int, float) or
                not math.isfinite(meta['simulation_time_s']) or
                abs(meta['simulation_time_s'] - frame['time_s']) > .001):
            raise ValueError('original graph frame/time join differs')
        nodes = graph.get('nodes')
        if not isinstance(nodes, list) or not nodes:
            raise ValueError('original graph participants missing')
        egos = [node for node in nodes if node.get('id') == 'ego']
        if len(egos) != 1 or type(egos[0].get('attributes', {}).get('actor_id')) is not int:
            raise ValueError('original graph ego identity missing')
        current_actor = egos[0]['attributes']['actor_id']
        if actor_id is None:
            actor_id = current_actor
        elif actor_id != current_actor:
            raise ValueError('original graph ego identity changed')
    if not diagnostic:
        binding = acquisition.get('map_binding', {})
        if binding.get('public_highway_reviewed') is not True:
            raise ValueError('reviewed public-highway source unavailable')
        survey = _source(attempt, acquisition, 'survey-packet.json')
        if _sha(survey) != binding.get('survey_packet_sha256'):
            raise ValueError('reviewed survey packet differs from Native map binding')
        packet = json.loads(survey.read_text())
        review = packet.get('public_highway_review', {})
        source = review.get('source', {}) if isinstance(review, dict) else {}
        original_review = _source(attempt, acquisition,
                                  'public-highway-review-source')
        if (review.get('status') != 'reviewed' or
                source.get('sha256') != _sha(original_review) or
                review.get('opendrive_sha256') != binding.get('opendrive_sha256') or
                review.get('approach_road_id') != binding.get('intersection_context', {}).get('approach_road_id') or
                review.get('departure_road_id') != binding.get('intersection_context', {}).get('departure_road_id')):
            raise ValueError('reviewed public-highway source differs from Native binding')
    return {'case_id': case_id, 'checks': ['native_source', 'all_participants',
            'time_join', 'full_video_decode', 'actual_pixels', 'physical_completion'],
            'decoded_frames': pixels['decoded_frames'], 'physical_status': physical['status'],
            'source_integrity_passed': True, 'diagnostic_fixture': diagnostic,
            'delivery_accepted': not diagnostic, 'legal_judgment': 'unresolved'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--case', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--allow-diagnostic', action='store_true')
    args = parser.parse_args()
    result = audit(args.attempt, args.case, allow_diagnostic=args.allow_diagnostic)
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
