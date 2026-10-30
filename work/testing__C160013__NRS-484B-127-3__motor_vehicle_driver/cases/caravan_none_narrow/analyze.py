"""Saved-source measurements with explicit Native/fixture provenance; physical completion is separate from legal acceptance."""
import argparse, hashlib, json
from pathlib import Path
from worker_exchange.native_output import write_result

def required(root, name):
    path = root / name
    if not path.is_file():
        raise ValueError('Missing required source: ' + name)
    return path

def rows(root):
    value = [json.loads(s) for s in required(root, 'caravan_history.jsonl').read_text().splitlines() if s]
    if not value:
        raise ValueError('No original caravan samples')
    for r in value:
        if set(r['participants']) != {'front', 'subject', 'rear', 'entrant'}:
            raise ValueError('Incomplete caravan actor roles')
    return value

def bounds(actor):
    vertices = actor['body_vertices_m']
    if len(vertices) < 4:
        raise ValueError('Incomplete participant body')
    return (min((v[0] for v in vertices)), max((v[0] for v in vertices)))

def caravan_spacing(root):
    samples = []
    for row in rows(root):
        p = row['participants']
        front = bounds(p['front'])[0] - bounds(p['subject'])[1]
        rear = bounds(p['subject'])[0] - bounds(p['rear'])[1]
        samples.append({'frame': row['frame'], 'time_s': row['time_s'], 'front_clear_gap_m': front, 'rear_clear_gap_m': rear, 'front_speed_mps': p['front']['speed_mps'], 'subject_speed_mps': p['subject']['speed_mps'], 'rear_speed_mps': p['rear']['speed_mps']})
    return {'samples': samples, 'minimum_front_gap_m': min((x['front_clear_gap_m'] for x in samples)), 'minimum_rear_gap_m': min((x['rear_clear_gap_m'] for x in samples)), 'scope': 'original body-vertex clear gaps; legal sufficient-space threshold unresolved'}

def entrant_occupancy(root):
    observations = []
    for row in rows(root):
        p = row['participants']
        lo, hi = bounds(p['entrant'])
        rear_front = bounds(p['rear'])[1]
        subject_rear = bounds(p['subject'])[0]
        observations.append({'frame': row['frame'], 'time_s': row['time_s'], 'entrant_lane_id': p['entrant']['lane_id'], 'entrant_rear_clearance_m': lo - rear_front, 'entrant_front_clearance_m': subject_rear - hi, 'whole_entrant_between_pair': lo > rear_front and hi < subject_rear})
    return {'samples': observations, 'observed_between_pair_samples': sum((x['whole_entrant_between_pair'] for x in observations)), 'scope': 'geometric occupancy only; no safety or danger verdict'}

def outside_district_context(root):
    context = json.loads(required(root, 'caravan_context.json').read_text())
    return {'district': context['district'], 'group_roles': context['group_roles'], 'outsider_role': context['outsider_role'], 'formation': context.get('formation', 'caravan'), 'tow_configuration': context.get('tow_configuration', 'none'), 'road_id': context['road_id'], 'public_highway_status': context['public_highway_status'], 'source': context['source']}

def finalize(root, output):
    cfg = json.loads(required(root, 'config.json').read_text())
    spacing = caravan_spacing(root)
    entrant = entrant_occupancy(root)
    context = outside_district_context(root)
    sha = lambda n: hashlib.sha256(required(root, n).read_bytes()).hexdigest()
    report = {'format': 'worker-analysis-report-v1', 'case_id': cfg['selected_case_id'], 'measurements': {'caravan_full_body_gaps': {'method': 'caravan_spacing', 'value': spacing, 'sources': {'caravan_history.jsonl': sha('caravan_history.jsonl')}}, 'outsider_entry_clearances': {'method': 'entrant_occupancy', 'value': entrant, 'sources': {'caravan_history.jsonl': sha('caravan_history.jsonl')}}, 'outside_district_caravan_context': {'method': 'outside_district_context', 'value': context, 'sources': {'caravan_context.json': sha('caravan_context.json')}}}, 'limitations': ['Three-frame fixture is diagnostic only.', 'Actual Native entrant feasibility, other traffic and no-danger judgment require GPU/source review.']}
    output.write_text(json.dumps(report, indent=2) + '\n')
    traces = [json.loads(s) for s in required(root, 'trace.jsonl').read_text().splitlines() if s]
    history = rows(root)
    channels = root / 'channels'
    channels.mkdir(exist_ok=True)
    for n, f in [('kin.speed', 'speed_mps'), ('kin.velocity', 'velocity_mps')]:
        (channels / (n + '.jsonl')).write_text(''.join((json.dumps({'time_s': r['time_s'], 'value': r[f]}) + '\n' for r in traces)))
    (channels / 'caravan_history.jsonl').write_text(''.join((json.dumps({'time_s': r['time_s'], 'value': r}) + '\n' for r in history)))
    case = cfg['case']
    result = {'case_id': case['case_id'], 'measured_values': {'minimum_rear_gap_m': spacing['minimum_rear_gap_m'], 'observed_entry_samples': entrant['observed_between_pair_samples']}, 'target_checks': [{'target': 'caravan_spacing_sampled', 'requested': 'full-body gaps and outsider clearance', 'measured': len(spacing['samples']), 'method': 'caravan_spacing', 'tolerance': 0, 'matched': bool(spacing['samples']), 'physical_cause_confirmed': False, 'cause_evidence': 'caravan_history.jsonl'}], 'termination_reason': 'saved analysis; Native checks pending', 'physical_failure_flags': {'detection_validated': False}, 'trace_reference': 'trace.jsonl', 'video_references': ['raw.mkv'], 'video_frame_map_reference': 'video_frames.jsonl', 'recording_description': case['recording_description'], 'recording_evidence': [{'name': n, 'unit': u, 'reference': p} for n, u, p in [('kin.speed', 'm/s', 'channels/kin.speed.jsonl'), ('kin.velocity', 'm/s', 'channels/kin.velocity.jsonl'), ('caravan_history', 'structured record', 'channels/caravan_history.jsonl')]]}
    write_result(root, physical_result(root, result))
    return report

# update002 selected analyzer
from worker_exchange.native_output import physical_result,finalize_report
def prepare_saved(root):
    return {'status': 'not_required', 'outputs': []}

def finalize_selected(root,output):
    if (root/'acquisition-context.json').is_file():prepare_saved(root)
    value=finalize(root,output)
    finalize_report(root,output)
    return value

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--attempt', required=True)
    p.add_argument('--output', required=True)
    a = p.parse_args()
    finalize_selected(Path(a.attempt), Path(a.output))
