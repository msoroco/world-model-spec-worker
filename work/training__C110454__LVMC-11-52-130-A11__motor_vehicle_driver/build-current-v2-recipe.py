"""Bind one 600-frame parking diagnostic to portable source bytes."""
import hashlib
import json
from pathlib import Path
import shutil
import argparse

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RAW = ('native_samples.jsonl', 'native_parking_history.json', 'video_frames.jsonl',
       'trace.jsonl', 'body_history.jsonl', 'road_geometry.json', 'context.json',
       'capture/evidence.jsonl', 'capture/manifest.json', 'capture/recorder_info.txt',
       'capture/native/frames.jsonl')

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--case', choices=('witness_1','witness_2'),default='witness_1')
    parser.add_argument('--attempt', type=Path)
    args=parser.parse_args()
    case=args.case
    attempt=(args.attempt or ROOT/f'.runtime-work/c110454-current-profile/saved-attempt-v5-{case}').resolve()
    source=HERE/'current-v2-source'/case
    source.mkdir(parents=True, exist_ok=True)
    for name in RAW:
        target = source / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(attempt / name, target)
    frame_path = source / 'capture/native/frames.jsonl'
    frames = [json.loads(x) for x in frame_path.read_text().splitlines()]
    samples = [json.loads(x) for x in (source / 'native_samples.jsonl').read_text().splitlines()]
    assert len(frames) == len(samples) == 600
    graphs = []
    for frame, sample in zip(frames, samples):
        assert frame['frame'] == sample['native_frame']
        path = f"capture/native/graphs/{frame['frame']:08d}.adapter.json"
        frame['adapter_graph'] = 'graphs/' + f"{frame['frame']:08d}.adapter.json"
        x, y = sample['native_center_xy_m']
        graphs.append({'path': path,
                       'attributes': {'frame': frame['frame'], 'simulation_time_s': frame['time_s']},
                       'nodes': [{'id': 'ego', 'attributes': {
                           'vertex': [x, y, 0.5], 'sem_class': 'ego',
                           'forward': [1.0, 0.0, 0.0], 'entity_id': 107,
                           'carla_speed': sample['speed_m_s'], 'special_class': 'ego'}}],
                       'edges': []})
    frame_path.write_text(''.join(json.dumps(x, separators=(',', ':')) + '\n' for x in frames))
    videos = [{'path': name + '.mkv', 'frames': 600, 'width': w, 'height': h,
               'fps': 20, 'color': color} for name, w, h, color in (
                   ('overview', 1920, 1080, 'blue'),
                   ('approach', 1280, 720, 'green'),
                   ('reference_corner', 1280, 720, 'white'),
                   ('driver_reference', 1280, 720, 'red'))]
    spec = {'files': {}, 'graphs': graphs, 'videos': videos}
    spec_path = HERE / f'current-v2-{case}-generator.json'
    spec_path.write_text(json.dumps(spec, separators=(',', ':')) + '\n')
    assert spec_path.stat().st_size < 2 * 1024 * 1024
    recipe = {'format': 'worker-fixture-recipe',
              'sources': [{'path': name, 'source': str((source / name).relative_to(ROOT)),
                           'sha256': sha(source / name)} for name in RAW],
              'generator': {'source': str(spec_path.relative_to(ROOT)),
                            'sha256': sha(spec_path)}}
    recipe_path = HERE / f'current-v2-{case}-recipe.json'
    recipe_path.write_text(json.dumps(recipe, indent=2) + '\n')
    manifest = json.loads((HERE / 'draft-current-primary-manifest.json').read_text())
    manifest['format'] = 'worker-unselected-current-v2-probe-manifest'
    contract = json.loads((HERE / f'draft-measurement-contracts/{case}/measurement-contract.json').read_text())
    contract['format'] = 'worker-measurement-contract'
    contract['status'] = 'unselected_diagnostic'
    contract_path = HERE / f'current-v2-{case}-measurement-contract.json'
    contract_path.write_text(json.dumps(contract, indent=2) + '\n')
    entry=next(x for x in manifest['cases'] if x['case_id'].endswith('__'+case))
    entry['measurement_contract'] = str(contract_path.relative_to(HERE))
    entry['fixture_recipe'] = str(recipe_path.relative_to(ROOT))
    if case=='witness_2':
        prior=HERE/'current-v2-witness_1-recipe.json'
        prior_contract=HERE/'current-v2-witness_1-measurement-contract.json'
        manifest['cases'][0]['fixture_recipe']=str(prior.relative_to(ROOT))
        manifest['cases'][0]['measurement_contract']=str(prior_contract.relative_to(HERE))
    manifest_path = HERE / 'current-v2-probe-manifest.json'
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    assert max((source / name).stat().st_size for name in RAW) < 2 * 1024 * 1024
    print(json.dumps({'manifest_sha256': sha(manifest_path),
                      'recipe_sha256': sha(recipe_path), 'generator_sha256': sha(spec_path),
                      'source_count': len(RAW), 'frames': len(frames), 'videos': len(videos)}))

if __name__ == '__main__':
    main()
