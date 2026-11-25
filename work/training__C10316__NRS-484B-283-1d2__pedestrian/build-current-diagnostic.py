"""Build source-hashed 600-frame textual fixtures for public CPU compatibility.

Inputs are generated diagnostics. Black videos test source joins and decoding,
not legibility of a real countdown or a governing physical device.
"""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SIBLING = ROOT / 'work/training__C10316__NRS-484B-283-1d3__pedestrian/diagnostic30-controlled_1.json'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def lines(text):
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def encoded(rows):
    return ''.join(json.dumps(row, separators=(',', ':'), allow_nan=False) + '\n' for row in rows)


def build():
    original = json.loads(SIBLING.read_text())
    source_root = Path(json.loads((HERE / 'draft-countdown-measurement-summary.json').read_text())['retained_root'])
    # The public fixture generator uses exactly this RGB24 black-frame source.
    black_rgb_sha = hashlib.sha256(bytes(1280 * 720 * 3)).hexdigest()
    for suffix in ('probe_01', 'probe_02'):
        source = source_root / suffix
        samples = lines((source / 'countdown_samples.jsonl').read_text())
        if len(samples) != 600:
            raise ValueError('Full synthetic countdown source missing')
        diagnostic = json.loads(json.dumps(original))
        files = diagnostic['files']
        files.pop('no-countdown-context.json')
        files.pop('no-countdown-samples.jsonl')
        context = json.loads((source / 'countdown-context.json').read_text())
        context['introductory_exceptions'] = {
            'status': 'unverified_synthetic_request',
            'cited_sections': ['NRS 484B.287', 'NRS 484B.290', 'NRS 484B.350']}
        files['countdown-context.json'] = json.dumps(context, separators=(',', ':')) + '\n'
        files['countdown_samples.jsonl'] = encoded([
            dict(sample, original_display_frame_sha256=black_rgb_sha)
            for sample in samples])
        evidence = lines(files['capture/evidence.jsonl'])
        trace = lines(files['trace.jsonl'])
        mapping = lines(files['video_frames.jsonl'])
        if len(evidence) != 600 or len(trace) != 600 or len(mapping) != 600 or len(diagnostic['graphs']) != 600:
            raise ValueError('Template diagnostic source incomplete')
        for index, (sample, event, motion, frame_map, graph) in enumerate(zip(
                samples, evidence, trace, mapping, diagnostic['graphs'])):
            x, y = sample['pedestrian_xy_m']
            body = [[point[0], point[1], z]
                    for point in sample['pedestrian_footprint_xy_m'] for z in (0, 1.8)]
            if sample['native_frame'] != index + 100 or abs(sample['time_s'] - index / 20) > 1e-8:
                raise ValueError('Countdown diagnostic frame/time differs')
            event['ego']['position_m'] = [x, y, .5]
            event['ego']['body_vertices_m'] = body
            event['ego']['speed_mps'] = 8.14 / 8
            event['ego']['speed_provenance'] = 'synthetic_native_sample'
            motion['position'] = {'x': x, 'y': y, 'z': .5}
            motion['position_m'] = [x, y, .5]
            motion['speed_mps'] = 8.14 / 8
            motion['speed_mph'] = (8.14 / 8) * 2.2369362921
            motion['velocity_mps'] = [8.14 / 8, 0, 0]
            frame_map['source_rgb_sha256'] = {'driver_reference': black_rgb_sha}
            node = graph['nodes'][0]['attributes']
            node['vertex'] = [x, y, .5]
            node['threedbbox'] = body
            graph['attributes']['source'] = 'C10316 synthetic countdown source'
        files['capture/evidence.jsonl'] = encoded(evidence)
        files['trace.jsonl'] = encoded(trace)
        files['video_frames.jsonl'] = encoded(mapping)
        manifest = json.loads(files['capture/manifest.json'])
        manifest['sources']['trace.jsonl'] = hashlib.sha256(files['trace.jsonl'].encode()).hexdigest()
        manifest['sources']['road.xodr'] = sha(HERE / 'native/road.xodr')
        files['capture/manifest.json'] = json.dumps(manifest, separators=(',', ':')) + '\n'
        for video in diagnostic['videos']:
            if video['path'] == 'reference_corner.mkv':
                video['path'] = 'reference_corner.mkv'
            elif video['path'] == 'driver_reference.mkv':
                video['path'] = 'driver_reference.mkv'
        output = HERE / ('diagnostic-current-' + suffix + '.json')
        output.write_text(json.dumps(diagnostic, separators=(',', ':'), allow_nan=False) + '\n')
        if output.stat().st_size > 2 * 1024 * 1024:
            raise ValueError('Returned textual diagnostic exceeds size limit')
        relative = output.relative_to(ROOT).as_posix()
        recipe = {'format': 'worker-fixture-recipe',
                  'sources': [{'path': 'diagnostic-input.json', 'source': relative,
                               'sha256': sha(output)}],
                  'generator': {'source': relative, 'sha256': sha(output)}}
        (HERE / ('diagnostic-current-' + suffix + '-recipe.json')).write_text(
            json.dumps(recipe, indent=2) + '\n')
        print(suffix, output.stat().st_size, sha(output), flush=True)


if __name__ == '__main__':
    build()
