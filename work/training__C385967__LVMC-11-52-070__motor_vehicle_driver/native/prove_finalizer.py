"""Recorded-only synthetic saved finalization positive and missing source negative."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess

from prove_saved_sources import FOLDER, HERE, SCRATCH, source, write, write_rows
from finalize import finalize


def main():
    receipt = {}
    for suffix, yaw in (('a',45),('b',225)):
        case = FOLDER.name+'__probe_'+suffix
        attempt = source(case, yaw)
        construction = json.loads((HERE/f'condition_{suffix}-primary-construction.json').read_text())
        config = json.loads(next(item['content'] for item in construction['files']
                                 if item['path']=='config.json'))
        write(attempt/'config.json', config)
        samples = [json.loads(line) for line in (attempt/'native_samples.jsonl').read_text().splitlines()]
        write_rows(attempt/'trace.jsonl', [{'frame': row['native_frame'],
            'time_s': row['time_s'], 'heading_deg': row['ego_front_yaw_deg']}
            for row in samples])
        (attempt/'capture').mkdir(exist_ok=True)
        write_rows(attempt/'capture/evidence.jsonl', [{'original_frame': row['native_frame'],
            'recording_time_s': row['time_s'], 'observations': []} for row in samples])
        for name in ('overview','approach','reference_corner','driver_reference'):
            path = attempt/(name+'.mkv')
            if not path.exists():
                subprocess.run(['ffmpeg','-nostdin','-hide_banner','-loglevel','error',
                    '-f','lavfi','-i','color=c=blue:s=32x32:r=20', '-frames:v','600',
                    '-an','-c:v','ffv1',str(path)],check=True,timeout=120)
        analysis = attempt/'analysis-report.json'
        if analysis.exists(): analysis.unlink()
        result_file = attempt/'result.json'
        if result_file.exists(): result_file.unlink()
        report = finalize(attempt, analysis)
        result = json.loads(result_file.read_text())
        expected = 'front_with_lawful_flow' if suffix=='a' else 'front_against_lawful_flow'
        if report['measurements']['parked_front_direction']['value'] != expected or \
                any(count != 600 for count in report['four_camera_frames'].values()) or \
                result['accepted'] or result['setup_confirmed'] or result['legal_verdict_claimed']:
            raise AssertionError('Saved finalizer positive differs')
        bad = SCRATCH/(f'finalizer-{suffix}-missing')
        bad.mkdir(exist_ok=True)
        for filename in ('config.json', 'road_geometry.json', 'parking_context.json',
                         'native_samples.jsonl', 'video_frames.jsonl',
                         'body_history.jsonl', 'trace.jsonl'):
            (bad/filename).write_bytes((attempt/filename).read_bytes())
        (bad/'capture').mkdir(exist_ok=True)
        (bad/'capture/evidence.jsonl').write_bytes((attempt/'capture/evidence.jsonl').read_bytes())
        try:
            finalize(bad, bad/'analysis-report.json')
        except ValueError as exc:
            if 'permission_authority.json' not in str(exc):
                raise
        else:
            raise AssertionError('Missing permission authority source was accepted')
        write(HERE/f'selected-{suffix}-saved-receipt.json', {
            'case_id':case,'recorded_only':True,'source_kind':'synthetic_cpu_fixture',
            'direction':expected,'four_camera_frames':report['four_camera_frames'],
            'missing_permission_source_rejected':True,
            'original_native_accepted':False,'city_permission_verified':False})
        receipt[suffix] = {'saved_positive':True,'missing_permission_rejected':True}
    print(json.dumps(receipt,sort_keys=True))


if __name__=='__main__': main()
