"""Independent 600-frame graph/source audit and saved-source tamper rejection."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ZONE = HERE / 'native' / 'zone'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def main():
    checks = []
    measurements = []
    for condition, letter in (('condition_a', 'a'), ('condition_b', 'b')):
        fixture = ROOT / '.runtime-work' / ('c10374-current-graph-' + letter)
        saved = ROOT / '.runtime-work' / ('c10374-current-saved-' + letter)
        recipe = json.loads((HERE / 'current-graph-fixture' /
                             (condition + '-recipe.json')).read_text())
        original = rows(fixture / 'native-raw-actors.jsonl')
        frames = rows(fixture / 'video_frames.jsonl')
        graph_rows = rows(fixture / 'capture/native/frames.jsonl')
        if len(original) != len(frames) or len(original) != len(graph_rows) or len(original) != 600:
            raise AssertionError('Retained source/graph interval differs')
        for item in recipe['sources']:
            if sha(fixture / item['path']) != item['sha256']:
                raise AssertionError('Explicit source hash changed')
        for i, (actor, frame, graph_row) in enumerate(zip(original, frames, graph_rows)):
            if (actor['frame'] != frame['video_frame'] or actor['frame'] != i or
                    actor['native_frame'] != frame['native_frame'] or
                    graph_row['frame'] != actor['native_frame']):
                raise AssertionError('Actor/video/graph frame join changed')
            graph = json.loads((fixture / 'capture/native' /
                                graph_row['adapter_graph']).read_text())
            if graph['format'] != 'native-adapter-graph-v1' or graph['metadata']['frame'] != actor['native_frame']:
                raise AssertionError('Live adapter graph changed')
            ego = next(node for node in graph['nodes'] if node['id'] == 'ego')['attributes']
            if (ego['vertex'] != actor['ego']['center_native_xyz_m'] or
                    ego['threedbbox'] != actor['ego']['body_native_xyz_m'] or
                    ego['carla_speed'] != actor['ego']['speed_mps']):
                raise AssertionError('Graph ego differs from retained actor')
        for name in ('forward', 'overview', 'reference_corner', 'driver_reference'):
            video = fixture / (name + '.mkv')
            probe = subprocess.run(['ffprobe', '-v', 'error', '-count_frames',
                                    '-select_streams', 'v:0', '-show_entries',
                                    'stream=codec_name,nb_read_frames', '-of', 'json',
                                    str(video)], capture_output=True, text=True, check=True)
            stream = json.loads(probe.stdout)['streams'][0]
            if stream['codec_name'] != 'ffv1' or stream['nb_read_frames'] != '600':
                raise AssertionError('Diagnostic camera frame contract changed')
        receipt = json.loads((saved / 'preparation-receipt.json').read_text())
        if receipt['raw_hashes']['native-raw-actors.jsonl'] != sha(fixture / 'native-raw-actors.jsonl'):
            raise AssertionError('Saved processor did not bind raw source')
        measure = json.loads((HERE / 'current-graph-fixture' /
                              (condition.replace('_', '-') + '-measurement.log')).read_text())
        if measure['source_kind'] != 'synthetic_cpu' or measure['delivery_ready']:
            raise AssertionError('Diagnostic measurement promoted to delivery')
        measurements.append(measure)
        checks.append({'condition': condition, 'joined_graphs': 600,
                       'ffv1_sources_decoded': 4,
                       'raw_source_sha256': sha(fixture / 'native-raw-actors.jsonl'),
                       'saved_preparation_sha256': sha(saved / 'preparation-receipt.json')})
    if measurements[0]['moving_body_rectangle_overlap_frames'] == \
            measurements[1]['moving_body_rectangle_overlap_frames']:
        raise AssertionError('Controlled zone-overlap measurement absent')
    source = ROOT / '.runtime-work/c10374-current-graph-a'
    negative = ROOT / '.runtime-work/c10374-current-graph-negative'
    negative.mkdir(exist_ok=True)
    for name in ('native-map-readback.json', 'native-raw-actors.jsonl',
                 'video_frames.jsonl', 'frame-review.jsonl',
                 'native-capture-report.json'):
        shutil.copyfile(source / name, negative / name)
    altered = rows(negative / 'native-raw-actors.jsonl')
    altered[100]['requested_ego_x_m'] = 999
    (negative / 'native-raw-actors.jsonl').write_text(
        ''.join(json.dumps(row) + '\n' for row in altered))
    bundle = ZONE / 'offline/bundles/selected_c5852cfd__condition_a/primary'
    target = ROOT / '.runtime-work/c10374-current-saved-negative'
    command = [sys.executable, str(ZONE / 'saved.py'), '--bundle', str(bundle),
               '--raw-folder', str(negative), '--saved-folder', str(target),
               '--synthetic-cpu']
    failure = subprocess.run(command, capture_output=True, text=True)
    if failure.returncode == 0 or 'actor/request join' not in failure.stderr:
        raise AssertionError('Changed source did not fail saved processing')
    receipt = {'format': 'c10374-current-live-graph-audit-v1',
               'checks': checks, 'negative_mutation': 'changed requested ego x at frame 100',
               'negative_rejected': True, 'overlap_frames': [
                   value['moving_body_rectangle_overlap_frames'] for value in measurements],
               'physical_zone_designation_claimed': False,
               'legal_verdict_claimed': False, 'passed': True}
    path = HERE / 'current-graph-fixture' / 'independent-audit.json'
    path.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'passed': True, 'audit_sha256': sha(path)}))


if __name__ == '__main__':
    main()
