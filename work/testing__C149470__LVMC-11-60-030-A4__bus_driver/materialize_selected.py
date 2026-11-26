"""Return exact selected constructions and configs for local review."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    for index, entry in enumerate(manifest['cases']):
        name = entry['case_id'].removeprefix(HERE.name + '__')
        construction = HERE / entry['construction']
        value = json.loads(construction.read_text())
        config = next(item['content'] for item in value['files']
                      if item['path'] == 'config.json')
        folder = HERE / 'cases' / name
        folder.mkdir(parents=True, exist_ok=True)
        (folder / 'construction.json').write_bytes(construction.read_bytes())
        (folder / 'config.json').write_text(config, encoding='utf-8')
        if index == 0:
            root_construction = dict(value)
            root_construction['measurement_plan'] = {
                'case_id': entry['case_id'], 'original_frames': 900,
                'procedure': 'analysis.py', 'legal_judgment': 'unresolved',
                'source_packets': ['reviewed-site.json', 'original-bus-frames.jsonl',
                                   'camera-frame-map.jsonl', 'four original PNG archives']}
            root_construction['static_checks'] = [
                'exact non-tour bus, operator, public-street and qualifying loading place',
                'reviewed curb, bus and separate traffic route geometry',
                '900 joined 20 Hz original frames and four camera streams']
            root_construction['termination_rules'] = [
                '900 original frames at 20 Hz',
                'fail closed on absent reviewed source, geometry or camera join']
            root_construction['mechanisms'] = [
                'reviewed Native site and candidate packet',
                'source-gated bus approach, halt and loading actors',
                'source-sealed four-camera Native capture']
            (HERE / 'construction.json').write_text(
                json.dumps(root_construction, indent=2, ensure_ascii=False) + '\n',
                encoding='utf-8')
            (HERE / 'config.json').write_text(config, encoding='utf-8')
            for item in value['files']:
                target = HERE / item['path']
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(item['content'], encoding='utf-8')
        for candidate in entry.get('candidates', []):
            destination = folder / candidate['id']
            destination.mkdir(parents=True, exist_ok=True)
            (destination / 'construction.json').write_bytes((HERE / candidate['construction']).read_bytes())
    print('materialized selected constructions:', len(manifest['cases']))


if __name__ == '__main__':
    main()
