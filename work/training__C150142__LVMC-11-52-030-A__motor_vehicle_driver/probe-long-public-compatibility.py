"""Build a source-bound diagnostic long fixture for the pinned public CLI."""
import hashlib
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SCRATCH = REPO / '.runtime-work/owner150142/long-public-probe'
SOURCES = HERE / 'public-probe-sources'
CASE = HERE.name + '__tour_bus_below'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, obj):
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + '\n')


def main():
    SOURCES.mkdir(exist_ok=True)
    for name in ('trace.jsonl', 'native-raw-actors.jsonl',
                 'native-passenger-actors.jsonl', 'capture-evidence.jsonl'):
        src = HERE / ('current-tour-bus-below-' + name + '.zlib64')
        shutil.copyfile(src, SOURCES / name)
    shutil.copyfile(HERE / 'current-tour-bus-below-compact-video_frames.jsonl',
                    SOURCES / 'video_frames.jsonl')
    for name in ('overview', 'approach', 'reference_corner', 'driver_reference'):
        src = SCRATCH / ('overview-black-x264.mkv' if name == 'overview'
                         else 'detail-black-x264.mkv')
        shutil.copyfile(src, SOURCES / (name + '.mkv'))
    attempt = REPO / '.runtime-work/owner150142/long-selected-v1/tour_bus_below/attempt'
    for name in ('statutory-context.json', 'native-map-readback.json'):
        shutil.copyfile(attempt / name, SOURCES / name)
    original = json.loads((HERE / 'current-runtime-runner-drafts/tour_bus_below/primary/construction.json').read_text())
    finalizer = next(item for item in original['files'] if item['path'] == 'finalize_selected.py')
    code = finalizer['content']
    code = code.replace('import math\n', 'import math\nimport base64\nimport zlib\n')
    old = "return [json.loads(line) for line in source(attempt, name).read_text().splitlines()\n            if line.strip()]"
    new = """content = source(attempt, name).read_bytes()
    if name in ('trace.jsonl', 'native-raw-actors.jsonl',
                'native-passenger-actors.jsonl'):
        content = zlib.decompress(base64.b64decode(content, validate=True))
    result = [json.loads(line) for line in content.splitlines() if line.strip()]
    if name == 'video_frames.jsonl':
        for i, row in enumerate(result):
            row['native_frame'] = i
            row['views'] = sorted(VIEWS)
    return result"""
    assert old in code
    code = code.replace(old, new)
    old = "    channels=attempt/'channels'; channels.mkdir()"
    new = """    trace_path = attempt/'trace-expanded.jsonl'
    trace_path.write_bytes(zlib.decompress(base64.b64decode(
        source(attempt, 'trace.jsonl').read_bytes(), validate=True)))
    map_path = attempt/'video-frames-expanded.jsonl'
    map_path.write_text(''.join(json.dumps(row, separators=(',',':'))+'\\n'
                                for row in frame_map))
    channels=attempt/'channels'; channels.mkdir()"""
    assert old in code
    code = code.replace(old, new)
    code = code.replace("'trace_reference':'trace.jsonl'", "'trace_reference':'trace-expanded.jsonl'")
    code = code.replace("'video_frame_map_reference':'video_frames.jsonl'", "'video_frame_map_reference':'video-frames-expanded.jsonl'")
    finalizer['content'] = code
    construction = HERE / 'current-tour-bus-below-public-probe-construction.json'
    write_json(construction, original)
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    entry = next(item for item in manifest['cases'] if item['case_id'] == CASE)
    entry['construction'] = construction.name
    entry['construction_sha256'] = sha(construction)
    recipe = HERE / 'current-tour-bus-below-public-probe-recipe.json'
    names = ['trace.jsonl', 'native-raw-actors.jsonl', 'native-passenger-actors.jsonl',
             'video_frames.jsonl', 'statutory-context.json', 'native-map-readback.json']
    names += [name + '.mkv' for name in ('overview', 'approach', 'reference_corner', 'driver_reference')]
    items = [{'path': name, 'source': str((SOURCES/name).relative_to(REPO)),
              'sha256': sha(SOURCES/name)} for name in names]
    items.append({'path':'capture/evidence.jsonl',
                  'source':str((SOURCES/'capture-evidence.jsonl').relative_to(REPO)),
                  'sha256':sha(SOURCES/'capture-evidence.jsonl')})
    write_json(recipe, {'format':'worker-fixture-recipe', 'sources':items})
    entry['fixture_recipe'] = str(recipe.relative_to(REPO))
    draft = HERE / 'current-tour-bus-below-public-probe-manifest.json'
    write_json(draft, manifest)
    print(json.dumps({'manifest': str(draft.relative_to(REPO)),
                      'recipe': str(recipe.relative_to(REPO)),
                      'construction_sha256': sha(construction)}, sort_keys=True))


if __name__ == '__main__':
    main()
