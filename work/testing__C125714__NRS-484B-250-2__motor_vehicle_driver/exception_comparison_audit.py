"""Independent source-bound comparison of C125714 exception diagnostics."""
from __future__ import annotations

import argparse
import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

from delivery_audit import audit_sources, observed_left_turn

BASE = 'testing__C125714__NRS-484B-250-2__motor_vehicle_driver__'
PAIRS = {
    'device_governance_exception': ('timing_inside_training', 'official_device_controlled'),
    'opposite_turn_realization': ('opposite_intends_left', 'opposite_makes_left'),
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def load(root, suffix):
    path = Path(root) / suffix
    site = json.loads((path/'site-context.json').read_text())
    diagnostic = (path/'original-bindings.json').is_file()
    binding_path = path/('original-bindings.json' if diagnostic else 'source-manifest.json')
    bindings = json.loads(binding_path.read_text())
    acquisition = json.loads((path/'acquisition.json').read_text())
    if not diagnostic:
        audit_sources(path, BASE+suffix)
    names = ('road.xodr','site-context.json','ego-body-history.jsonl',
             'other-body-history.jsonl')
    for name in names:
        binding = bindings.get(name, acquisition.get(name, {}))
        if (binding.get('kind') != ('diagnostic_fixture' if diagnostic else 'original_native') or
                binding.get('sha256') != sha(path/name)):
            raise ValueError('source-bound exception comparison changed: '+name)
    if site.get('case_id') != BASE+suffix:
        raise ValueError('exact exception comparison case identity changed')
    return {'path':path,'site':site,'bindings':bindings,
            'ego':rows(path/'ego-body-history.jsonl'),
            'other':rows(path/'other-body-history.jsonl'),
            'frames':rows(path/'video_frames.jsonl'), 'diagnostic_fixture':diagnostic,
            'controller':rows(path/'controller-history.jsonl')
                if (path/'controller-history.jsonl').is_file() else []}


def road_without_signals(path):
    root = ET.fromstring(path.read_bytes())
    for road in root.findall('road'):
        signals = road.find('signals')
        if signals is not None:road.remove(signals)
    return ET.tostring(root,encoding='utf-8')


def compare(root, comparison_id):
    if comparison_id not in PAIRS:
        raise ValueError('unknown exception comparison')
    left_suffix,right_suffix=PAIRS[comparison_id]
    left,right=(load(root,suffix) for suffix in (left_suffix,right_suffix))
    if left['diagnostic_fixture'] != right['diagnostic_fixture']:
        raise ValueError('comparison mixes diagnostic and original Native sources')
    diagnostic=left['diagnostic_fixture']
    a,b=left['site'],right['site']
    fixed=('crossing_id','roadway_id','intersection_polygon_xy_m',
           'subsection_4_context_reviewed')
    if diagnostic:fixed+=('ego_actor_id','other_actor_id')
    for key in fixed:
        if a.get(key)!=b.get(key):
            raise ValueError('fixed exception comparison context changed: '+key)
    if diagnostic:
        if left['frames'] != right['frames'] or left['ego'] != right['ego']:
            raise ValueError('fixed original frame or ego motion changed')
    else:
        if (len(left['frames']) != len(right['frames']) or
                a.get('ego_route_xyz_m') != b.get('ego_route_xyz_m') or
                len(left['controller']) != len(left['frames']) or
                len(right['controller']) != len(right['frames'])):
            raise ValueError('fixed Native capture length, ego route or controls changed')
        for name in ('ego_release_s','other_release_s'):
            if left['controller'][0].get(name) != right['controller'][0].get(name):
                raise ValueError('fixed original release schedule changed: '+name)
    if comparison_id == 'device_governance_exception':
        for key in ('ego_side','other_side',
                    'approach_relation','other_left_turn_intent'):
            if a.get(key)!=b.get(key):
                raise ValueError('fixed crossing condition changed: '+key)
        if ((diagnostic and left['other'] != right['other']) or
                (not diagnostic and a.get('other_route_xyz_m') != b.get('other_route_xyz_m')) or
                road_without_signals(left['path']/'road.xodr') !=
                road_without_signals(right['path']/'road.xodr')):
            raise ValueError('device comparison changed other motion or road geometry')
        signals=ET.fromstring((right['path']/'road.xodr').read_bytes()).findall('.//signal')
        if (a.get('official_device_controls_intersection') is not False or
                b.get('official_device_controls_intersection') is not True or
                not any(s.get('id')==b.get('official_device_id') for s in signals)):
            raise ValueError('declared governing-device difference missing')
    else:
        for key in ('ego_highway','other_highway','approach_relation',
                    'official_device_controls_intersection','other_left_turn_intent'):
            if a.get(key)!=b.get(key):
                raise ValueError('fixed opposite-turn condition changed: '+key)
        if sha(left['path']/'road.xodr') != sha(right['path']/'road.xodr'):
            raise ValueError('fixed opposite-turn map changed')
        if (diagnostic and left['other'][0] != right['other'][0]) or (
                not diagnostic and a.get('other_route_xyz_m',[None])[0] !=
                b.get('other_route_xyz_m',[None])[0]):
            raise ValueError('fixed other initial approach changed')
        if (a.get('other_left_turn_making') is not False or
                b.get('other_left_turn_making') is not True or
                observed_left_turn(right['other'], b.get('intersection_polygon_xy_m')) is not True):
            raise ValueError('declared original left-turn difference missing')
    return {'format':'worker-c125714-exception-comparison-cpu-v1',
            'comparison_id':comparison_id,'case_ids':[a['case_id'],b['case_id']],
            'source_sha256':[{name:sha(item['path']/name) for name in
                ('road.xodr','site-context.json','ego-body-history.jsonl',
                 'other-body-history.jsonl','video_frames.jsonl')}
                for item in (left,right)],
            'fixed_conditions_verified':True,'declared_difference_verified':True,
            'diagnostic_fixture':diagnostic,'legal_exception_applies':'unresolved',
            'physical_acceptance_claimed':False}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--sources',type=Path,required=True)
    parser.add_argument('--comparison',choices=tuple(PAIRS),required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result=compare(args.sources,args.comparison)
    args.output.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(args.comparison,'fixed and declared source differences passed')


if __name__=='__main__':main()
