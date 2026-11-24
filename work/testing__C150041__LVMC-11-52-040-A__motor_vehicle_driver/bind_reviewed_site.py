"""Bind separate reviewed stand/park packets to one six-case site plan.

This constructs CPU scene requests only. Review labels in test packets do not
establish a real road, Chapter exception, Native motion, or legal judgment.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from parking_pose import REQUESTS
from parking_scene import build
from parking_sweep_feasibility import reviewed_placement_grid
from source_review import validate


def bind(park_packet: Path, stand_packet: Path, *, edge_offset_m=2.5,
         approach_distance_m=8.0) -> dict:
    packets = {'park': Path(park_packet), 'stand': Path(stand_packet)}
    contexts = {kind: validate(path, source_root=path.parent)
                for kind, path in packets.items()}
    for kind, context in contexts.items():
        if context['activity'] != kind:
            raise ValueError('reviewed packet activity differs: ' + kind)
    common = ('roadway_source', 'road_edge_source',
              'lawful_direction_source', 'chapter_exception_source',
              'road_edge_xy_m', 'roadway_polygon_xy_m', 'lawful_travel_xy',
              'chapter_exception_review')
    for key in common:
        if contexts['park'][key] != contexts['stand'][key]:
            raise ValueError('stand/park fixed reviewed site differs: ' + key)
    surveys = {}
    for kind, path in packets.items():
        packet = json.loads(path.read_text())
        survey_path = path.parent / 'reviewed-survey.json'
        survey_bytes = survey_path.read_bytes()
        if hashlib.sha256(survey_bytes).hexdigest() != packet.get('survey_sha256'):
            raise ValueError('retained reviewed survey seal differs: ' + kind)
        survey = json.loads(survey_bytes)
        if (survey.get('native_map', {}).get('name') !=
                packet.get('context', {}).get('native_map_name') or
                survey.get('native_map', {}).get('opendrive_sha256') !=
                contexts[kind]['roadway_source']):
            raise ValueError('retained reviewed Native map differs: ' + kind)
        surveys[kind] = survey
    for key in ('native_map',):
        if surveys['park'][key] != surveys['stand'][key]:
            raise ValueError('stand/park Native map differs')
    if not surveys['park']['native_map'].get('name'):
        raise ValueError('reviewed Native map name missing')
    scenes = {}
    for suffix, (activity, _, _) in REQUESTS.items():
        packet = packets[activity]
        scene = build(packet, packet.parent, suffix,
                      approach_distance_m=approach_distance_m)
        if scene['source_packet_sha256'] != hashlib.sha256(packet.read_bytes()).hexdigest():
            raise ValueError('scene and reviewed packet seal differ')
        scenes[suffix] = scene
    for activity in ('park', 'stand'):
        reference = scenes[activity + '_parallel_lawful']
        for variation in ('angled_lawful', 'parallel_reverse'):
            scene = scenes[activity + '_' + variation]
            if (scene['target_pose']['target_center_xy_m'] !=
                    reference['target_pose']['target_center_xy_m'] or
                    scene['source_hashes'] != reference['source_hashes']):
                raise ValueError('comparison fixed reviewed placement differs')
    for variation in ('parallel_lawful', 'angled_lawful', 'parallel_reverse'):
        park, stand = scenes['park_' + variation], scenes['stand_' + variation]
        if (park['target_pose']['target_center_xy_m'] !=
                stand['target_pose']['target_center_xy_m'] or
                park['target_pose']['target_forward_xy'] !=
                stand['target_pose']['target_forward_xy']):
            raise ValueError('stand/park placement differs')
    grid = reviewed_placement_grid(packets['park'], packets['park'].parent,
                                   edge_offsets_m=(edge_offset_m,))
    angles = grid['offsets'][0]['feasible_angles_deg']
    if 0 not in angles or 30 not in angles:
        raise ValueError('reviewed roadway cannot contain required full-body poses')
    return {'format': 'parking-reviewed-six-case-binding-v1',
            'native_map': surveys['park']['native_map'],
            'packet_sha256': {kind: contexts[kind]['reviewed_packet_sha256']
                              for kind in packets},
            'reviewed_source_hashes': {key: contexts['park'][key]
                                       for key in common[:4]},
            'edge_offset_m': edge_offset_m,
            'scenes': scenes, 'placement_grid': grid,
            'source_kind': 'separate_retained_reviewed_site_packets',
            'physical_realization_claimed': False,
            'legal_judgment': 'unresolved'}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--park-packet', required=True)
    parser.add_argument('--stand-packet', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    output = Path(args.output)
    if output.exists():
        raise ValueError('retain prior binding output; choose a fresh path')
    output.write_text(json.dumps(bind(args.park_packet, args.stand_packet),
                                 indent=2) + '\n')


if __name__ == '__main__':
    main()
