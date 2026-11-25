"""Materialize source-identity preserving partial C80909 CPU constructions."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
ASSIGNMENT = 'testing__C80909__NRS-484B-227-1__motor_vehicle_driver'
SUFFIXES = ('left_through_opening', 'left_across_blocked_divider',
            'left_at_established_crossover', 'left_right_roadway_continuation')
MODULES = ('runner.py', 'left_turn_route.py', 'barrier_construction.py',
           'native_capture.py', 'camera_encoder.py', 'divider_measurements.py',
           'saved_finalizer.py', 'build_diagnostic_packets.py')


def _build_once():
    for suffix in SUFFIXES:
        case = ASSIGNMENT + '__' + suffix
        folder = ROOT / 'cases' / suffix
        config = {'assignment_id': ASSIGNMENT, 'law_id': 'NRS-484B-227-1',
                  'cell_id': 'C80909', 'actor': 'motor_vehicle_driver',
                  'selected_case_id': case,
                  'supported_case_ids': [ASSIGNMENT + '__' + value for value in SUFFIXES],
                  'rate_hz': 20, 'duration_s': 30,
                  'required_atoms': [], 'source_packets': [],
                  'physical_completion': {
                      'criterion': 'travel_progress' if suffix == 'left_right_roadway_continuation' else 'turn',
                      'motion_source': 'movement_history.jsonl',
                      'body_key': 'ego_body_vertices_xy_m',
                      'heading_key': 'heading_deg',
                      'road_key': 'road_id',
                      'turn_sign': 1,
                      'destination_road': None,
                      'engineering_tolerances_not_legal': True},
                  'cameras': [{'name': name, 'width': width, 'height': height,
                               'fov_deg': 90, 'pose_strategy': 'source-reviewed-site-pose'}
                              for name, width, height in (
                                  ('overview',1920,1080), ('approach',1280,720),
                                  ('reference_corner',1280,720), ('driver_reference',1280,720))]}
        config_path = ROOT / 'config.json' if suffix == SUFFIXES[0] else folder / 'config.json'
        config_path.write_text(json.dumps(config, indent=2) + '\n')
        files = []
        def add(source, destination):
            files.append({'path': destination, 'source': source.relative_to(REPO).as_posix(),
                          'content': source.read_text()})
        for name in MODULES:
            add(ROOT / name, name)
        for source in sorted((ROOT / 'tests').glob('test*.py')):
            add(source, 'tests/' + source.name)
        add(config_path, 'config.json')
        add(folder / 'site-plan.json', 'site-plan.json')
        add(folder / 'diagnostic-site.json', 'diagnostic-site.json')
        authority = folder / 'diagnostic-authority.txt'
        if authority.is_file():add(authority, 'diagnostic-authority.txt')
        for variant in SUFFIXES:
            for source in sorted((ROOT / 'cases' / variant).glob('*')):
                if (source.name in ('construction.json', 'config.json') or
                        source.suffix == '.log' or
                        source.name.endswith(('-diagnostic-sources.json', '-fixture-recipe.json'))):
                    continue
                add(source, 'cases/' + variant + '/' + source.name)
        channels = [
            {'name': name, 'unit': unit, 'method': method,
             'sampling_rate_hz': 20, 'time_window': '30 seconds at 20 Hz',
             'reference_frame': 'original Native tick and four cameras',
             'uncertainty': 'physical realization and legal judgment require independent review'}
            for name, unit, method in (
                ('ego_body', 'm', 'original complete Native world vertices'),
                ('other_body', 'm', 'original complete Native world vertices'),
                ('ego_heading', 'degrees', 'original Native pose yaw'),
                ('divider_overlap', 'boolean', 'complete body against sourced divider polygon'),
                ('camera_frames', 'frame', 'four original RGB source frames joined to Native tick'))]
        construction = {
            'case_id': case, 'law_id': 'NRS-484B-227-1', 'cell_id': 'C80909',
            'actor': 'motor_vehicle_driver', 'entrypoint': 'runner.py',
            'status': 'partial_cpu_diagnostic_unreviewed_native_site',
            'files': files,
            'recording_description': {'channels': channels,
                'context_inputs': [
                    {'name': 'divider_site', 'unit': 'structured record',
                     'method': 'source-hashed divided-highway roadway and opening geometry',
                     'source_refs': ['divider_context.json', 'site_source_receipt.json'],
                     'uncertainty': 'actual divided-highway and public-authority status require review'},
                    {'name': 'barrier_opening', 'unit': 'structured record',
                     'method': 'realized Native barrier section vertices and open footprint',
                     'source_refs': ['barrier_receipt.json'],
                     'uncertainty': 'actual vertical clearance and crossing require review'}],
                'limitations': ['Diagnostic packet is synthetic; Native site and authority review pending']},
            'measurement_plan': {'raw_sources': [
                'road.xodr','trace.jsonl','carla_recorder.log','capture/manifest.json',
                'divider_context.json','barrier_receipt.json','site_source_receipt.json',
                'movement_history.jsonl','video_frames.jsonl','control_history.jsonl',
                'overview.mkv','approach.mkv','reference_corner.mkv','driver_reference.mkv'],
                'analysis_entrypoint': 'saved_finalizer.py',
                'saved_processing_status': 'authored; runtime-bound proof pending'},
            'static_checks': ['runner.py --check checks exact diagnostic route without CARLA',
                              'tests exercise barrier, routes, cameras and saved source rejections'],
            'termination_rules': ['600 synchronized original frames at 20 Hz',
                                  'close original recorder and FFV1 encoders before actor cleanup',
                                  'restore owner world with readback before capture seal'],
            'mechanisms': ['source-gated reviewed Native site packet for physical capture',
                           'two realized barrier sections and complete-body route clearance',
                           'four original FFV1 camera streams and canonical FrameMap identities',
                           'PipelineCapture graph, telemetry and original Native recorder']}
        config['case'] = {'case_id': case,
                          'recording_description': construction['recording_description']}
        config_path.write_text(json.dumps(config, indent=2) + '\n')
        for item in files:
            if item['path'] == 'config.json':
                item['content'] = config_path.read_text()
        destination = ROOT / 'construction.json' if suffix == SUFFIXES[0] else folder / 'construction.json'
        destination.write_text(json.dumps(construction, indent=2) + '\n')


def build():
    # The first pass writes every case config; the second embeds their final bytes.
    _build_once()
    _build_once()


if __name__ == '__main__':build()
