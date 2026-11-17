"""Return bounded textual diagnostics for selected emergency vehicle cases."""
import hashlib
import argparse
import json
import pickle
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path.insert(0, str(REPO / 'runtime/pipeline/scenario_pipeline'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--slug', choices=(
        'emergency_vehicle_signed_business', 'emergency_vehicle_signed_no_business',
        'emergency_vehicle_unsigned_business', 'emergency_vehicle_unsigned_no_business'),
        default='emergency_vehicle_signed_business')
    slug = parser.parse_args().slug
    case_id = ROOT.name + '__' + slug
    source_names = {
        'emergency_vehicle_signed_business': 'emergency-signed-business',
        'emergency_vehicle_signed_no_business': 'emergency-signed-no-business',
        'emergency_vehicle_unsigned_business': 'emergency-business',
        'emergency_vehicle_unsigned_no_business': 'emergency-no-business',
    }
    source_root = REPO / ('.runtime-work/c150142-' + source_names[slug] +
                          '-primary-native-v1')
    config = json.loads((source_root / 'config.json').read_text())
    if config['case_id'] != case_id or config['capture_frames'] != 361:
        raise ValueError('Diagnostic identity or frame count changed')
    files = {}
    participant = ('native-business-worker-inventory.jsonl' if slug.endswith('_no_business')
                   else 'native-service-worker-actors.jsonl')
    for name in ('road.xodr', 'statutory-context.json',
                 'native-raw-actors.jsonl', participant,
                 'native-map-readback.json',
                 'video_frames.jsonl', 'trace.jsonl', 'acquisition-provenance.json',
                 'capture/evidence.jsonl', 'capture/native/frames.jsonl',
                 'capture/recorder_info.txt', 'capture/manifest.json'):
        path = source_root / name
        if not path.is_file():
            raise ValueError('Missing retained source: ' + name)
        files[name] = path.read_text()
    graphs = []
    for path in sorted((source_root / 'capture/native/graphs/base').glob('*.pkl')):
        with path.open('rb') as stream:
            graph = pickle.load(stream)
        if graph.nodes or graph.edges:
            raise ValueError('Unexpected diagnostic graph geometry')
        graphs.append({'path': path.relative_to(source_root).as_posix(),
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
    folder = ROOT / 'selected-diagnostics' / slug
    folder.mkdir(parents=True, exist_ok=True)
    spec = folder / 'primary.json'
    spec.write_text(json.dumps({'files': files, 'graphs': graphs, 'videos': videos},
                               separators=(',', ':'), ensure_ascii=False,
                               allow_nan=False) + '\n')
    if spec.stat().st_size > 2 * 1024 * 1024:
        raise ValueError('Returned source exceeds 2 MiB')
    relative = spec.relative_to(REPO).as_posix()
    recipe = folder / 'primary-recipe.json'
    recipe.write_text(json.dumps({'format': 'worker-fixture-recipe',
                                  'sources': [{'path': 'diagnostic-source.json',
                                               'source': relative, 'sha256': sha(spec)}],
                                  'generator': {'source': relative, 'sha256': sha(spec)}},
                                 indent=2) + '\n')
    print(json.dumps({'case_id': case_id, 'graph_count': len(graphs),
                      'source_bytes': spec.stat().st_size,
                      'recipe_sha256': sha(recipe),
                      'source_kind': 'synthetic_native_sample'}))


if __name__ == '__main__':
    main()
