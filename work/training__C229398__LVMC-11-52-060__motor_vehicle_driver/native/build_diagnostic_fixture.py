"""Build the source-inventoried 15-foot diagnostic fixture and recipe."""
import hashlib
import json
import shutil
import tempfile
from pathlib import Path

from prove_finalize_saved import fixture

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent
ROOT = PACKAGE.parents[1]
SUFFIX = 'at_15_ft'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def build():
    manifest_path = PACKAGE / 'draft-primary-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    entry = next(item for item in manifest['cases'] if item['case_id'].endswith('__' + SUFFIX))
    construction = json.loads((PACKAGE / entry['construction']).read_text())
    source_dir = PACKAGE / 'diagnostic-fixture' / SUFFIX / 'sources'
    source_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=ROOT / '.runtime-work') as temporary:
        attempt = Path(temporary) / 'attempt'
        fixture(attempt, construction, 15)
        names = ('acquisition-provenance.json', 'native-curb-proposal.json',
                 'reviewed-curb.json', 'native-raw-actors.jsonl', 'trace.jsonl',
                 'video_frames.jsonl')
        sources = []
        for name in names:
            destination = source_dir / name
            shutil.copyfile(attempt / name, destination)
            sources.append({'path': name, 'source': str(destination.relative_to(ROOT)),
                            'sha256': sha(destination)})
    trace = [json.loads(line) for line in (source_dir / 'trace.jsonl').read_text().splitlines()]
    raw = [json.loads(line) for line in (source_dir / 'native-raw-actors.jsonl').read_text().splitlines()]
    if len(trace) != 600 or len(raw) != 600:
        raise ValueError('Diagnostic source interval is incomplete')
    road = ('<OpenDRIVE><header revMajor="1" revMinor="4" name="C229398-synthetic-curb-diagnostic" '
            'version="1" north="100" south="-100" east="100" west="-100" />'
            '<road id="1" name="straight-curb-diagnostic" length="100" junction="-1">'
            '<link /><planView><geometry s="0" x="-50" y="-1.75" hdg="0" length="100">'
            '<line /></geometry></planView><elevationProfile><elevation s="0" a="0" b="0" c="0" d="0" />'
            '</elevationProfile><lanes><laneOffset s="0" a="0" b="0" c="0" d="0" />'
            '<laneSection s="0"><left><lane id="1" type="driving" level="false">'
            '<width sOffset="0" a="3.5" b="0" c="0" d="0" /></lane></left>'
            '<center><lane id="0" type="none" level="false" /></center>'
            '<right><lane id="-1" type="driving" level="false">'
            '<width sOffset="0" a="3.5" b="0" c="0" d="0" /></lane></right>'
            '</laneSection></lanes><objects /><signals /></road></OpenDRIVE>\n')
    evidence, frames, graphs = [], [], []
    for row, actors in zip(trace, raw):
        frame = row['frame']
        index = actors['frame']
        time_s = row['time_s']
        center = row['position_m']
        box = [[center[0]-0.5, center[1]-0.5, 0],
               [center[0]+0.5, center[1]-0.5, 0],
               [center[0]+0.5, center[1]+0.5, 0],
               [center[0]-0.5, center[1]+0.5, 0]]
        relative = f'graphs/base/{frame:08d}.adapter.json'
        evidence.append({'original_frame': frame, 'recording_time_s': time_s,
                         'replay_frame': frame, 'replay_simulation_time_s': time_s,
                         'actor_id': 107,
                         'ego': {'body_vertices_m': box, 'heading_deg': 0.0,
                                 'position_m': center, 'speed_mps': 0.0,
                                 'speed_provenance': 'synthetic_native_sample'},
                         'world': {'road_projection': {'lane_id': -1, 'road_id': 1,
                                                        's_m': 50.0, 'section_id': 0}},
                         'synthetic_diagnostic': True})
        frames.append({'frame': frame, 'simulation_time': time_s,
                       'adapter_graph': relative, 'base': relative,
                       'nodes': 1, 'edges': 0})
        graphs.append({'path': 'capture/native/' + relative,
                       'attributes': {'frame': frame, 'simulation_time_s': time_s,
                                      'synthetic_diagnostic': True},
                       'nodes': [{'id': 'ego', 'attributes': {
                           'sem_class': 'ego', 'entity_id': 107,
                           'vertex': center, 'forward': [1, 0, 0],
                           'threedbbox': box}}], 'edges': []})
    files = {'road.xodr': road,
             'capture/recorder_info.txt': 'Create 107: vehicle.tesla.model3\n',
             'capture/evidence.jsonl': ''.join(json.dumps(row, separators=(',', ':')) + '\n'
                                               for row in evidence),
             'capture/native/frames.jsonl': ''.join(json.dumps(row, separators=(',', ':')) + '\n'
                                                   for row in frames)}
    files['capture/manifest.json'] = json.dumps({
        'case_id': entry['case_id'], 'frames': 600, 'extraction_confirmed': True,
        'synthetic_diagnostic': True,
        'sources': {'road.xodr': hashlib.sha256(road.encode()).hexdigest(),
                    'trace.jsonl': sha(source_dir / 'trace.jsonl')}},
        separators=(',', ':')) + '\n'
    videos = []
    for name in ('overview', 'approach', 'reference_corner', 'driver_reference'):
        videos.append({'path': name + '.mkv', 'frames': 600,
                       'width': 1920 if name == 'overview' else 1280,
                       'height': 1080 if name == 'overview' else 720,
                       'fps': 20, 'color': 'black'})
    spec_path = source_dir.parent / 'diagnostic-generator.json'
    write(spec_path, {'files': files, 'graphs': graphs, 'videos': videos})
    recipe_path = source_dir.parent / 'fixture-recipe.json'
    write(recipe_path, {'format': 'worker-fixture-recipe', 'sources': sources,
                        'generator': {'source': str(spec_path.relative_to(ROOT)),
                                      'sha256': sha(spec_path)}})
    entry['fixture_recipe'] = str(recipe_path.relative_to(ROOT))
    write(manifest_path, manifest)
    proposals = PACKAGE / 'proposals/cases.json'
    if not proposals.is_file():
        plan = json.loads((PACKAGE / 'case-plan.json').read_text())
        write(proposals, {'cell_id': plan['cell_id'], 'actor': plan['actor'],
                          'status': 'draft_diagnostic', 'cases': plan['cases']})
    print(json.dumps({'case_id': entry['case_id'], 'source_count': len(sources),
                      'recipe_sha256': sha(recipe_path)}))


if __name__ == '__main__':
    build()
