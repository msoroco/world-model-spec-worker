"""Finalize a saved overpass crossing from original, hash-bound sources.

This measures a requested crossing sequence and records unresolved legal review.
Synthetic fixtures exercise software paths only.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from overpass_source import audit_saved, sha


REQUIRED = ('scene.json', 'candidate-overpass.xodr', 'body-history.jsonl',
            'video_frames.jsonl', 'trace.jsonl', 'original-sources.json',
            'reviewed-site.json', 'reviewed-site-source.txt',
            'municipal-designation-source.txt')
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def _source(root, name):
    path = root/name
    if not path.is_file():
        raise ValueError('Missing required source: '+name)
    return path


def measure_crossing_order(audit):
    m = audit['measurement']
    return {key:m[key] for key in ('pedestrian_road_entry_frame',
           'pedestrian_road_exit_frame', 'vehicle_crossing_pass_frame',
           'pedestrian_entered_after_vehicle_passed',
           'simultaneous_engineering_conflict_frames')}


def measure_roadway_vehicle_inventory(audit):
    m = audit['measurement']
    return {'observed_native_vehicle_actor_ids':m['observed_native_vehicle_actor_ids'],
            'reviewed_roadway_y_bounds_m':m['reviewed_roadway_y_bounds_m'],
            'classification':'reviewed surface bounds and original Native inventory'}


def measure_provided_overhead_crossing(audit):
    return {'map_sha256':audit['source_hashes']['map'],
            'reviewed_site_source_sha256':audit['source_hashes']['site_review_source'],
            'crossing_location':'surface roadway beneath reviewed overhead crossing'}


def measure_designated_place(audit):
    return audit['measurement']['reviewed_municipal_designation']


def analyze(attempt, output):
    from worker_exchange.native_output import physical_result, provenance_kind, write_result

    root = Path(attempt).resolve()
    output = Path(output).resolve()
    if output != root/'analysis-report.json' or output.exists() or (root/'result.json').exists():
        raise ValueError('fresh local analysis report and result required')
    for name in (*REQUIRED, *(camera+'.mkv' for camera in CAMERAS)):
        _source(root, name)
    config = json.loads(_source(root, 'config.json').read_text())
    scene = json.loads((root/'scene.json').read_text())
    if config.get('selected_case_id') != scene['case_id']:
        raise ValueError('selected case differs from original scene')
    diagnostic = config.get('diagnostic_only') is True or provenance_kind(root) == 'synthetic_fixture'
    audit = audit_saved(root, diagnostic=diagnostic)
    frames = [json.loads(line) for line in (root/'video_frames.jsonl').read_text().splitlines() if line]
    trace = [json.loads(line) for line in (root/'trace.jsonl').read_text().splitlines() if line]
    if len(frames) != len(trace) or any(
            t.get('frame') != f.get('carla_frame', f.get('frame')) or
            abs(t.get('time_s', -1)-f['time_s']) > 1e-4 for t,f in zip(trace,frames)):
        raise ValueError('original trace and frame-map time join differs')
    values = {'crossing_order':(measure_crossing_order(audit),
                               ('body-history.jsonl','video_frames.jsonl')),
              'roadway_vehicle_inventory':(measure_roadway_vehicle_inventory(audit),
                                           ('body-history.jsonl','reviewed-site.json')),
              'provided_overhead_crossing':(measure_provided_overhead_crossing(audit),
                                            ('reviewed-site.json',
                                             'reviewed-site-source.txt')),
              'designated_place_prohibition':(measure_designated_place(audit),
                                              ('reviewed-site.json',
                                               'municipal-designation-source.txt'))}
    methods = {'crossing_order':'measure_crossing_order',
               'roadway_vehicle_inventory':'measure_roadway_vehicle_inventory',
               'provided_overhead_crossing':'measure_provided_overhead_crossing',
               'designated_place_prohibition':'measure_designated_place'}
    report = {'format':'worker-analysis-report','analysis_complete':True,
              'case_id':scene['case_id'],
              'provenance_kind':'synthetic_fixture' if diagnostic else 'native',
              'diagnostic_fixture':diagnostic,
              'measurements':{key:{'method':methods[key], 'value':value,
                              'sources':{name:sha(root/name) for name in sources}}
                              for key,(value,sources) in values.items()},
              'legal_verdict_claimed':False,
              'limitations':['Source review and diagnostic measurements do not prove physical visibility or legal priority.']}
    description = config['recording_description']
    channels = root/'channels'
    channels.mkdir()
    evidence = []
    for channel in description['channels']:
        name = channel['name']
        if name not in values:
            raise ValueError('unsupported overpass channel: '+name)
        path = channels/(name+'.jsonl')
        with path.open('x') as stream:
            for frame in frames:
                stream.write(json.dumps({'time_s':frame['time_s'],
                                         'value':values[name][0]},allow_nan=False)+'\n')
        evidence.append({'name':name,'unit':channel['unit'],
                         'reference':str(path.relative_to(root))})
    result = {'case_id':scene['case_id'],
              'measured_values':{key:value for key,(value,_) in values.items()},
              'target_checks':[{'target':'requested overpass crossing order',
                                'requested':scene['requested_hold_until_vehicle_passes'],
                                'measured':values['crossing_order'][0]['pedestrian_entered_after_vehicle_passed'],
                                'method':'original pedestrian and roadway vehicle frame order',
                                'tolerance':0,
                                'matched':scene['requested_hold_until_vehicle_passes'] ==
                                          values['crossing_order'][0]['pedestrian_entered_after_vehicle_passed'],
                                'physical_cause_confirmed':False,
                                'cause_evidence':audit['source_hashes']}],
              'setup_confirmed':False,'behavior_attempted':False,
              'maneuver_completed':False,'termination_reason':'Saved source review pending',
              'physical_failure_flags':[], 'trace_reference':'trace.jsonl',
              'video_references':[camera+'.mkv' for camera in CAMERAS],
              'video_frame_map_reference':'video_frames.jsonl',
              'recording_description':description,'recording_evidence':evidence,
              'realized_observables':{},'legal_judgment':'unresolved'}
    result = physical_result(root, result)
    write_result(root, result)
    report['physical_checks'] = result['physical_checks']
    report['realized_observables'] = result['realized_observables']
    output.write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    report = analyze(args.attempt, args.output)
    print(json.dumps({'case_id':report['case_id'],
                      'diagnostic_fixture':report['diagnostic_fixture']}))


if __name__ == '__main__':
    main()
