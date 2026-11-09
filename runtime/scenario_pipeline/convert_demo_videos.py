#!/usr/bin/env python3
"""Create frame-preserving browser playback copies without changing raw evidence."""
import argparse
import fcntl
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import os
from pathlib import Path
import subprocess

from batch_pipeline.store import atomic
from speed_overlay import write_overlay,ass_filter
from review_recordings import archive_report


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def probe(path):
    return json.loads(subprocess.check_output([
        'ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0',
        '-show_entries', 'stream=codec_name,width,height,nb_read_frames,avg_frame_rate:format=duration',
        '-of', 'json', str(path)], text=True, timeout=1800))


def convert(source, expected):
    with source.with_suffix('.webm.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        return _convert(source,expected)


def _convert(source, expected):
    destination = source.with_suffix('.webm')
    receipt_path = source.with_suffix('.webm.json')
    source_sha = digest(source)
    overlay_sha=None;overlay=None
    trace_path=source.parent/'trace.jsonl';mapping_path=source.parent/'video_frames.jsonl'
    if trace_path.exists() and mapping_path.exists():
        trace=[json.loads(line) for line in trace_path.read_text().splitlines()]
        mapping=[json.loads(line) for line in mapping_path.read_text().splitlines()]
        dimensions=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height,r_frame_rate','-of','json',str(source)],text=True))['streams'][0]
        num,den=map(int,dimensions['r_frame_rate'].split('/'))
        overlay=source.with_suffix('.measured-speed.ass')
        overlay_sha=write_overlay(overlay,trace,mapping,0,len(mapping),dimensions['width'],dimensions['height'],dimensions['height']-28,fps=num/den)
    coverage_sha=None;coverage=None
    if overlay:
        coverage=source.with_suffix('.trace-coverage.txt')
        coverage_text='Full delivered trace: %.3f-%.3f s | %d frames'%(mapping[0]['time_s'],mapping[-1]['time_s'],len(mapping))
        review_path=source.parent/'measured_review.json'
        speed_review=json.loads(review_path.read_text()).get('speed_evaluation') if review_path.exists() else None
        if speed_review:
            coverage_text+='\nFull-trace numeric label: %s | %d applicable exceedances'%(speed_review['expected_speed_rule_label'],len(speed_review['exceedance_frames']))
            window=speed_review.get('sample_window_s')
            coverage_text+='\nTarget-attainment window: '+('%.3f-%.3f s'%tuple(window) if window else 'unavailable')
        coverage.write_text(coverage_text)
        coverage_sha=hashlib.sha256(coverage.read_bytes()).hexdigest()
    scenario_sha=None;scenario_ass=source.with_suffix('.scenario.ass')
    if overlay:
        from scenario_overlay import write_overlay as write_scenario_overlay
        scenario_sha=write_scenario_overlay(scenario_ass,source.parent,mapping,dimensions['width'],dimensions['height'],top=90,fps=num/den)
    if receipt_path.is_file() and destination.is_file():
        prior = json.loads(receipt_path.read_text())
        if prior['source_sha256'] == source_sha and prior['sha256'] == digest(destination) and prior.get('speed_overlay_sha256')==overlay_sha and prior.get('trace_coverage_sha256')==coverage_sha and prior.get('scenario_overlay_sha256')==scenario_sha:
            return prior
    temporary = source.with_suffix('.pending.webm')
    command = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-i', str(source),
               '-map', '0:v:0', '-an', '-c:v', 'libvpx-vp9', '-crf', '24', '-b:v', '0',
               '-deadline', 'good', '-cpu-used', '5', '-threads', '4',
               '-pix_fmt', 'yuv420p', '-vsync', '0', str(temporary)]
    if overlay:
        font=str(next(p for p in [Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'),Path('/usr/share/fonts/truetype/LiberationSans-Regular.ttf')] if p.exists()))
        filters='setpts=PTS-STARTPTS,drawbox=x=0:y=0:w=iw:h=86:color=black:t=86,'+ass_filter(overlay)+',drawtext=fontfile='+font+':textfile='+str(coverage)+':x=8:y=8:fontsize=14:fontcolor=white:box=1:boxcolor=black@0.8'
        if speed_review and speed_review.get('sample_window_s'):
            a,b=speed_review['sample_window_s'];indices=[i for i,r in enumerate(mapping) if a<=r['time_s']<=b]
            if indices:
                active='between(n,%d,%d)'%(indices[0],indices[-1])
                filters+=",drawtext=fontfile=%s:text='Target-attainment window active':x=8:y=62:fontsize=14:fontcolor=yellow:box=1:boxcolor=black@0.8:enable='%s'"%(font,active)
                filters+=",drawtext=fontfile=%s:text='Outside target-attainment window':x=8:y=62:fontsize=14:fontcolor=white:box=1:boxcolor=black@0.8:enable='not(%s)'"%(font,active)
        if scenario_sha:filters+=','+ass_filter(scenario_ass)
        command[-1:-1]=['-vf',filters]
    with source.with_suffix('.webm.stderr.log').open('w') as log:
        subprocess.run(command, stderr=log, check=True, timeout=7200)
    observed = probe(temporary)
    stream = observed['streams'][0]
    if expected is None:
        expected = probe(source)['streams'][0]
    elif not all(k in expected for k in ('width','height')):
        header=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height','-of','json',str(source)],text=True))['streams'][0]
        expected=dict(expected,**header)
    count = int(stream['nb_read_frames'])
    if stream['codec_name'] != 'vp9' or count != int(expected['nb_read_frames']):
        raise ValueError('WebM codec/frame count mismatch: ' + str(source))
    if (stream['width'], stream['height']) != (expected['width'], expected['height']):
        raise ValueError('WebM dimensions mismatch: ' + str(source))
    if digest(source) != source_sha:
        raise ValueError('Source video changed during conversion: ' + str(source))
    os.replace(temporary, destination)
    receipt = {'source': str(source), 'source_sha256': source_sha,
               'video': str(destination), 'reference': destination.name,
               'sha256': digest(destination), 'ffprobe': observed,
               'frames': count, 'command': command,
               'verification': 'Full decoded-frame scan; source frame count and dimensions preserved',
               'encoding': 'VP9 WebM, CRF24, yuv420p; lossy playback copy of retained original',
               'source_unchanged': True, 'frame_order': 'No frame-rate conversion, trimming or scaling; measured speed annotated when telemetry is available',
               'scenario_overlay_sha256':scenario_sha,'trace_coverage_sha256':coverage_sha,'trace_coverage':'Full delivered trace' if coverage else 'Comparison excerpts annotated per panel','measured_speed_overlay':overlay is not None,'speed_overlay_sha256':overlay_sha}
    archive_report(receipt_path)
    atomic(receipt_path, receipt)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--workers', type=int, default=4)
    args = parser.parse_args()
    output = args.output.resolve()
    index = json.loads((output / 'delivery_index.json').read_text())
    # Remove obsolete formal-evaluation metadata from current comparison receipts.
    for comparison in index.get('comparison_videos', []):
        manifest = Path(comparison['manifest'])
        data = json.loads(manifest.read_text())
        if 'legal_compliance_evaluated' in data:
            from review_recordings import archive_report
            archive_report(manifest)
            data.pop('legal_compliance_evaluated')
            atomic(manifest, data)
    expected = {}
    for entry in index['cells']:
        for case in entry['cases']:
            for receipt in case.get('final_video_receipts', []):
                expected[(Path(case['execution']) / receipt['reference']).resolve()] = receipt['ffprobe']['streams'][0]
    sources = set()
    skipped_diagnostics=[]
    for entry in index['cells']:
        for case in entry['cases']:
            if not case.get('execution'):continue
            if not case.get('decoder_passed'):
                skipped_diagnostics.append({'case_id':case['case_id'],'execution':case['execution'],'reason':'Unconfirmed or incomplete capture; originals retained, no full-trace playback assertion'})
                continue
            sources.update(p.resolve() for p in Path(case['execution']).glob('*.mkv'))
    for comparison in index.get('comparison_videos',[]):
        source=Path(comparison.get('source_video') or comparison['video']).resolve()
        receipt=comparison.get('source_final_video_receipt') or comparison.get('final_video_receipt')
        if receipt:expected[source]=receipt['ffprobe']['streams'][0]
        if source.suffix=='.mkv':sources.add(source)
    receipts, errors = [], []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(convert, source, expected.get(source)): source for source in sorted(sources)}
        for future in as_completed(futures):
            source = futures[future]
            try:
                receipt = future.result()
                receipts.append(receipt)
                print(json.dumps({'converted': str(source), 'completed': len(receipts),
                                  'total': len(sources), 'frames': receipt['frames']}), flush=True)
            except Exception as exc:
                errors.append({'source': str(source), 'error': str(exc)})
                print(json.dumps(errors[-1]), flush=True)
    report = {'status': 'passed' if not errors else 'failed', 'videos': len(receipts),
              'expected_videos': len(sources), 'original_mkvs_retained': True,
              'receipts': sorted(receipts, key=lambda r: r['source']), 'errors': errors,'skipped_unconfirmed_diagnostics':skipped_diagnostics}
    atomic(output / 'webm_conversion_audit.json', report)
    if errors:
        raise ValueError('WebM conversion failed; see webm_conversion_audit.json')
    by_source = {r['source']: r for r in receipts}
    for entry in index['cells']:
        for case in entry['cases']:
            case['playback_videos'] = [by_source[str(p.resolve())] for p in Path(case['execution']).glob('*.mkv') if str(p.resolve()) in by_source] if case.get('execution') else []
    for comparison in index.get('comparison_videos',[]):
        original = comparison.get('source_video') or comparison['video']
        receipt = by_source.get(str(Path(original).resolve()))
        if receipt is None:continue
        comparison.setdefault('source_video', original)
        if 'source_final_video_receipt' not in comparison:
            comparison['source_final_video_receipt']=comparison.get('final_video_receipt') or {'source_sha256':receipt['source_sha256'],'ffprobe':{'streams':[{k:receipt['ffprobe']['streams'][0][k] for k in ('width','height','nb_read_frames')}]},'verification':'Successful conversion checked the full original decoded frame count and dimensions; exact source SHA256 bound in conversion receipt. No repeated scan.'}
        comparison['video'] = receipt['video']
        comparison['final_video_receipt'] = receipt
    index['playback_format'] = 'webm'
    index['webm_conversion_audit'] = str(output / 'webm_conversion_audit.json')
    atomic(output / 'delivery_index.json', index)
    print(json.dumps({'status': 'passed', 'webm_videos': len(receipts)}), flush=True)


if __name__ == '__main__':
    main()
