"""Independent saved-original alley source, rolling-hour, media and delivery audit."""
import argparse
import hashlib
import json
from pathlib import Path

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')

def require(ok, message):
    if not ok:
        raise ValueError(message)

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line]

def max_rolling_hour(ledger):
    intervals = sorted((item['start_s'], item['end_s']) for item in ledger['parked_intervals'])
    low, high = ledger['span_start_s'], ledger['span_end_s'] - 3600
    require(low <= high, 'Missing original one-hour ledger span')
    starts = {low, high}
    for a, b in intervals:
        starts.update(x for x in (a, b, a-3600, b-3600) if low <= x <= high)
    return max(sum(max(0, min(s+3600,b)-max(s,a)) for a,b in intervals) for s in starts)

def audit(case, attempt):
    attempt = Path(attempt)
    required = ['original_alley_context.json','original_parking_ledger.json','alley-capture.jsonl',
                'trace.jsonl','video_frames.jsonl','acquisition-provenance.json','capture/evidence.jsonl',
                'result.json','analysis-report.json','event_review.webm','final-decode.json']
    for name in required:
        require((attempt/name).is_file(), 'Missing required source: ' + name)
    context = json.loads((attempt/required[0]).read_text())
    ledger = json.loads((attempt/required[1]).read_text())
    provenance = json.loads((attempt/'acquisition-provenance.json').read_text())
    require(context.get('assignment_id') == case.rsplit('__',1)[0] and
            context.get('parking_ledger_sha256') == sha(attempt/required[1]),
            'Original hour ledger/assignment source differs')
    require(context.get('alley_status') == 'source_surveyed_alley' and
            context.get('otherwise_lawful_review') == 'independently_reviewed',
            'Alley or otherwise-lawful source review missing')
    for key,document in context.get('source_documents',{}).items():
        require((attempt/document).is_file(), 'Missing required source: '+document)
        require(context.get(key) == sha(attempt/document), 'Original source document hash differs: '+key)
    require(ledger['span_end_s'] - ledger['span_start_s'] >= 3600,
            'Original one-hour source span missing')
    for item in ledger['parked_intervals']:
        require(item.get('vehicle_id') == context.get('vehicle_id') and
                item.get('within_alley') is True and item.get('otherwise_lawful_reviewed') is True,
                'Parked interval lacks alley/identity/lawful source')
    frames, mapping, trace = rows(attempt/'alley-capture.jsonl'),rows(attempt/'video_frames.jsonl'),rows(attempt/'trace.jsonl')
    require(len(frames) == len(mapping) == len(trace) == 600, 'Original 600-frame join missing')
    for i,(f,m,t) in enumerate(zip(frames,mapping,trace)):
        require(f.get('video_frame') == m.get('video_frame') == i and
                f.get('native_frame') == m.get('carla_frame') == t.get('frame') and
                abs(f.get('time_s',-1)-ledger['capture_start_s']-i/20)<1e-6 and
                set(f.get('source_cameras',{})) == set(CAMERAS) and
                all(f['source_cameras'][name] == i for name in CAMERAS) and
                f.get('vehicle_id') == context['vehicle_id'] and f.get('within_alley') is True,
                'Original Native/civil-time/camera/alley join differs')
    report = json.loads((attempt/'analysis-report.json').read_text())
    result = json.loads((attempt/'result.json').read_text())
    finding = report.get('measurements',{}).get('alley_duration',{}).get('value',{})
    require(result.get('case_id') == case and result.get('physical_checks') and
            finding.get('max_parked_seconds_in_sourced_rolling_hour') == max_rolling_hour(ledger) and
            finding.get('legal_compliance') == 'unassessed',
            'Independent rolling-hour measurement or result differs')
    require(result.get('physical_acceptance_claimed') is False and
            result.get('legal_verdict_claimed') is False,
            'Premature physical/legal acceptance')
    map_sha = sha(attempt/'video_frames.jsonl')
    for i,name in enumerate(CAMERAS+('raw',)):
        media=attempt/(name+'.mkv');receipt=attempt/('source-'+str(i)+'.json')
        require(media.is_file() and receipt.is_file(), 'Missing decoded original video: '+name)
        decoded=json.loads(receipt.read_text())
        require(decoded.get('passed') is True and decoded.get('frames') == 600 and
                decoded.get('video_sha256') == sha(media) and decoded.get('mapping_sha256') == map_sha and
                decoded.get('rgb_sequence_sha256'), 'Original video pixels/frame decode missing: '+name)
    final=json.loads((attempt/'final-decode.json').read_text())
    require(final.get('passed') is True and final.get('frames') == 600 and
            final.get('video_sha256') == sha(attempt/'event_review.webm') and
            final.get('rgb_sequence_sha256'), 'Final review pixels not decoded')
    require(provenance.get('provenance_kind') == 'synthetic_fixture' and
            provenance.get('diagnostic_fixture') is True,
            'CPU proof needs explicit synthetic provenance')
    return {'case_id':case,'original_frames':600,'camera_sources':4,
            'rolling_hour_seconds':max_rolling_hour(ledger),
            'requested_duration_not_used_as_observation':True,
            'synthetic_cpu_diagnostic_only':True,'original_acceptance_claimed':False}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--case',required=True);parser.add_argument('--attempt',required=True)
    args=parser.parse_args();print(json.dumps(audit(args.case,args.attempt),sort_keys=True))
