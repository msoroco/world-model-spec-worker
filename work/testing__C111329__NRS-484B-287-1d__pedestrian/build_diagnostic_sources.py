"""Build text-only, explicitly synthetic compatibility recipes for four cases."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / 'tests'))

from native_acquisition import acquire, save
from native_crossing import digest
from saved_media_audit import inventory_camera_sources
from capture_export import publish
from test_saved_process import PNGAdapter, site as example_site


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def ref(root, name, value):
    write(root / name, value)
    return {'path': name, 'sha256': sha(root / name)}


def build():
    draft = json.loads((HERE / 'execution-manifest.draft.json').read_text())
    draft['format'] = 'worker-execution-manifest'
    draft['runtime_manifest_sha256'] = sha(REPO / 'runtime/SOURCE-MANIFEST.json')
    plan = json.loads((HERE / 'case-plan.json').read_text())
    road = (HERE / 'diagnostic-road.xodr').read_bytes()
    for entry in draft['cases']:
        case_id = entry['case_id']
        suffix = case_id.removeprefix(HERE.name + '__')
        case = next(row for row in plan['cases'] if row['case_id'] == case_id)
        route = case['scenario_parameters']['route_kind']
        authorized = case['scenario_parameters']['source_backed_diagonal_authorization']
        root = HERE / 'cases' / suffix
        sources = root / 'diagnostic-sources'
        sources.mkdir(parents=True, exist_ok=True)
        stage = REPO / '.runtime-work' / 'c111329-diagnostic' / suffix
        if stage.exists():
            raise ValueError('retain prior diagnostic stage; choose clean scratch')
        stage.mkdir(parents=True)
        sampled_site = example_site()
        sampled_site['map_sha256'] = hashlib.sha256(road).hexdigest()
        sampled_site['devices'][0]['pedestrian_governance'] = 'diagonal' if authorized else 'adjacent'
        sampled_site['devices'][0]['state'] = 'permissive' if authorized else 'prohibitive'

        class Adapter(PNGAdapter):
            def read_devices(self):
                return [dict(sampled_site['devices'][0])]

        packet = acquire(Adapter(), site=sampled_site, site_sha256=digest(sampled_site),
                         case_id=case_id, route_kind=route, authorization=authorized,
                         blueprint_id='walker.pedestrian.0001', frames=3,
                         capture_root=stage)
        camera = inventory_camera_sources(packet, stage)
        site_ref = ref(sources, 'site.json', sampled_site)
        native_ref = ref(sources, 'native-acquisition.json', packet)
        camera_ref = ref(sources, 'camera-manifest.json', camera)
        declaration = {'format': 'c111329-original-source-v1', 'case_id': case_id,
                       'diagnostic_fixture': True, 'site_ref': site_ref,
                       'native_acquisition_ref': native_ref,
                       'camera_manifest_ref': camera_ref}
        declaration_ref = ref(sources, 'pedestrian-source.json', declaration)
        (stage / 'construction.json').write_text('{}\n')
        (stage / 'runner.py').write_text('# diagnostic\n')
        publish(stage, packet=packet, camera_manifest=camera, site=sampled_site,
                road_bytes=road, restoration_verified=True,
                expected_frames=3, diagnostic=True)
        text_files = {}
        for path in stage.rglob('*'):
            if not path.is_file() or path.suffix in ('.png', '.mkv'):
                continue
            relative = path.relative_to(stage).as_posix()
            if relative in ('construction.json', 'runner.py', 'capture-seal.json'):
                continue
            text_files[relative] = path.read_text(encoding='utf-8')
        videos = [{'path': name + '.mkv', 'frames': 3, 'width': width,
                   'height': height, 'fps': 20, 'color': 'black'}
                  for name, width, height in (('overview', 1920, 1080),
                                              ('approach', 1280, 720),
                                              ('reference_corner', 1280, 720),
                                              ('driver_reference', 1280, 720))]
        spec = root / 'diagnostic.json'
        write(spec, {'files': text_files, 'graphs': [], 'videos': videos})
        recipe = {'format': 'worker-fixture-recipe',
                  'sources': [{'path': item['path'],
                               'source': (sources / item['path']).relative_to(REPO).as_posix(),
                               'sha256': item['sha256']}
                              for item in (site_ref, native_ref, camera_ref, declaration_ref)],
                  'generator': {'source': spec.relative_to(REPO).as_posix(),
                                'sha256': sha(spec)}}
        write(root / 'fixture-recipe.json', recipe)
        keys = [('crossing_route', 'measure_crossing_route',
                 ['pedestrian-source.json', 'site.json', 'native-acquisition.json']),
                ('official_device_authority', 'measure_device_authority',
                 ['site.json', 'native-acquisition.json']),
                ('exception_context', 'measure_exception_context',
                 ['pedestrian-source.json'])]
        requirements = []
        for index, (key, method, inputs) in enumerate(keys):
            disposition = plan['requirement_dispositions'][index]
            requirements.append({'disposition_index': index,
                                 'requirement': disposition['requirement'],
                                 'source': disposition['source'],
                                 'output_key': key, 'method': method,
                                 'value_type': 'object',
                                 'kind': 'sourced_context' if index == 2 else 'measured',
                                 'inputs': inputs})
        write(root / 'measurement-contract.json', {
            'format': 'worker-measurement-contract', 'assignment_id': HERE.name,
            'case_id': case_id, 'requirements': requirements,
            'negative': {'remove': ['pedestrian-source.json'],
                         'error_contains': 'Missing required source: pedestrian-source.json'},
            'scope': 'synthetic CPU compatibility only; original Native sources required for delivery'})
        entry['measurement_contract'] = f'cases/{suffix}/measurement-contract.json'
        entry['measurement_procedure'] = {'entrypoint': 'analysis.py'}
        entry['fixture_recipe'] = f'work/{HERE.name}/cases/{suffix}/fixture-recipe.json'
        print(suffix, sha(spec)[:12])
    write(HERE / 'execution-manifest.cpu-draft.json', draft)


if __name__ == '__main__':
    build()
