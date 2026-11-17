"""Freeze a bounded, textual mail-deposit diagnostic from the prior CPU sample."""
import hashlib
import argparse
import json
import pickle
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SOURCES = {
    'mail_adjacent_deposit': '.runtime-work/c150142-mail-adjacent-primary-native-v3',
    'mail_no_box_deposit': '.runtime-work/c150142-mail-no-box-primary-native-v3',
    'mail_adjacent_no_deposit': '.runtime-work/c150142-mail-no-deposit-primary-native-v1',
}
sys.path.insert(0, str(REPO / 'runtime/pipeline/scenario_pipeline'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--slug', choices=tuple(SOURCES),
                        default='mail_adjacent_deposit')
    args = parser.parse_args()
    slug = args.slug
    source_root = REPO / SOURCES[slug]
    case_id = ROOT.name + '__' + slug
    config = json.loads((source_root / 'config.json').read_text())
    if config['case_id'] != case_id or config['capture_frames'] != 361:
        raise ValueError('Prior CPU diagnostic identity or frame count changed')
    files = {}
    participant_files = (('native-business-worker-inventory.jsonl',
                          'native-mail-parcel-absence.jsonl')
                         if slug == 'mail_adjacent_no_deposit'
                         else ('native-mail-worker-actors.jsonl',
                               'native-mail-parcel-inventory.jsonl'))
    for name in ('road.xodr', 'statutory-context.json',
                 'native-raw-actors.jsonl', 'video_frames.jsonl', 'trace.jsonl',
                 'native-map-readback.json', *participant_files,
                 'acquisition-provenance.json',
                 'capture/evidence.jsonl', 'capture/native/frames.jsonl',
                 'capture/recorder_info.txt', 'capture/manifest.json'):
        source = source_root / name
        if not source.is_file():
            raise ValueError('Missing retained diagnostic source: ' + name)
        files[name] = source.read_text()
    graphs = []
    for source in sorted((source_root / 'capture/native/graphs/base').glob('*.pkl')):
        with source.open('rb') as stream:
            graph = pickle.load(stream)
        if graph.nodes or graph.edges:
            raise ValueError('Unexpected diagnostic graph geometry')
        graphs.append({'path': source.relative_to(source_root).as_posix(),
                       'attributes': graph.graph, 'nodes': [], 'edges': []})
    if len(graphs) != 361:
        raise ValueError('Diagnostic graph sequence incomplete')
    videos = [{'path': name + '.mkv', 'frames': 361, 'width': width,
               'height': height, 'fps': 20, 'color': color}
              for name, width, height, color in (
                  ('overview', 1920, 1080, 'red'),
                  ('approach', 1280, 720, 'blue'),
                  ('reference_corner', 1280, 720, 'green'),
                  ('driver_reference', 1280, 720, 'white'))]
    target_dir = ROOT / 'selected-diagnostics' / slug
    target_dir.mkdir(parents=True, exist_ok=True)
    spec_path = target_dir / 'primary.json'
    spec_path.write_text(json.dumps({'files': files, 'graphs': graphs,
                                     'videos': videos}, separators=(',', ':'),
                                    ensure_ascii=False, allow_nan=False) + '\n')
    if spec_path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError('Returned diagnostic source exceeds 2 MiB')
    relative = spec_path.relative_to(REPO).as_posix()
    recipe = {'format': 'worker-fixture-recipe',
              'sources': [{'path': 'diagnostic-source.json', 'source': relative,
                           'sha256': sha(spec_path)}],
              'generator': {'source': relative, 'sha256': sha(spec_path)}}
    recipe_path = target_dir / 'primary-recipe.json'
    recipe_path.write_text(json.dumps(recipe, indent=2) + '\n')
    print(json.dumps({'case_id': case_id, 'graph_count': len(graphs),
                      'source_bytes': spec_path.stat().st_size,
                      'recipe': recipe_path.relative_to(REPO).as_posix(),
                      'recipe_sha256': sha(recipe_path),
                      'source_kind': 'synthetic_native_sample'}))


if __name__ == '__main__':
    main()
