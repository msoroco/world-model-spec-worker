"""Source-gated Native pedestrian crossing attempt."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
from native_crossing import crossing_plan, digest
from native_acquisition import acquire, save
from saved_media_audit import inventory_camera_sources
from reviewed_site import verify as verify_reviewed_site
from carla_adapter import CarlaCrossingAdapter
from capture_export import publish as publish_original
from analysis import analyze as analyze_saved


def check():
    root = Path(__file__).resolve().parent
    config = json.loads((root / 'config.json').read_text(encoding='utf-8'))
    plan = (root / 'case-plan.json').read_bytes()
    if hashlib.sha256(plan).hexdigest() != config['plan_sha256']:
        raise ValueError('C111329 case plan source changed')
    case_id = config['selected_case_id']
    expected = config['scenario_parameters']
    case = next((row for row in json.loads(plan)['cases'] if row['case_id'] == case_id), None)
    if case is None or case['scenario_parameters'] != expected:
        raise ValueError('C111329 exact case parameters changed')
    if config['fps'] != 20 or config['frame_count'] != 900 or config['cameras'] != ['overview','approach','reference_corner','driver_reference']:
        raise ValueError('C111329 original capture contract changed')
    if config['required_sources'] != ['original_map', 'intersection_corners', 'official_pedestrian_devices', 'walker_identity', 'original_camera_png']:
        raise ValueError('C111329 required sources changed')
    return case_id, expected


def source(root, ref):
    rel = ref.get('path')
    if not isinstance(rel, str) or not rel or Path(rel).is_absolute() or '..' in Path(rel).parts:
        raise ValueError('C111329 original source path invalid')
    candidate = root / rel
    if candidate.is_symlink():
        raise ValueError('C111329 original source symlinked')
    path = candidate.resolve(strict=True)
    if not path.is_relative_to(root.resolve()) or hashlib.sha256(path.read_bytes()).hexdigest() != ref.get('sha256'):
        raise ValueError('C111329 original source hash mismatch')
    return path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir')
    parser.add_argument('--host')
    parser.add_argument('--port', type=int)
    args = parser.parse_args()
    case_id, expected = check()
    if args.check:
        print('C111329 exact offline check passed: ' + case_id)
        return
    operator_path = os.environ.get('SCENARIO_C111329_ORIGINAL_OPERATOR')
    operator_sha = os.environ.get('SCENARIO_C111329_ORIGINAL_OPERATOR_SHA256')
    if not all((args.output_dir, args.host, args.port, operator_path, operator_sha)):
        raise ValueError('reviewed original C111329 site, device and Native operator required')
    operator = Path(operator_path).resolve(strict=True)
    if hashlib.sha256(operator.read_bytes()).hexdigest() != operator_sha:
        raise ValueError('reviewed original C111329 operator hash mismatch')
    spec = importlib.util.spec_from_file_location('c111329_operator', operator)
    if spec is None or spec.loader is None:
        raise ValueError('reviewed original C111329 operator cannot load')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    import carla
    client = carla.Client(args.host, args.port)
    client.set_timeout(30)
    world = client.get_world()
    attempt = Path(args.output_dir).resolve(strict=True)
    bindings = module.bind_original(world=world, case_id=case_id, attempt=attempt)
    if not isinstance(bindings, dict) or set(bindings) != {'site_ref', 'sensors', 'device_reader', 'blueprint_id', 'spawn_z'}:
        raise ValueError('reviewed original C111329 binding contract incomplete')
    site_ref = bindings['site_ref']
    blueprint_id = bindings['blueprint_id']
    site = json.loads(source(attempt, site_ref).read_text(encoding='utf-8'))
    if site.get('cell_id') != 'C111329' or site.get('actor') != 'pedestrian':
        raise ValueError('reviewed original C111329 site identity mismatch')
    verify_reviewed_site(attempt, site, expected['route_kind'], expected['source_backed_diagonal_authorization'])
    adapter = None
    try:
        adapter = CarlaCrossingAdapter(world, bindings['sensors'], bindings['device_reader'],
                                       blueprint_library=world.get_blueprint_library(),
                                       location_factory=carla.Location, transform_factory=carla.Transform,
                                       vector_factory=carla.Vector3D, walker_control_factory=carla.WalkerControl,
                                       spawn_z=bindings['spawn_z'])
        packet = acquire(adapter, site=site, site_sha256=digest(site), case_id=case_id,
                         route_kind=expected['route_kind'],
                         authorization=expected['source_backed_diagonal_authorization'],
                         blueprint_id=blueprint_id, frames=900, fps=20,
                         capture_root=attempt)
    finally:
        if adapter is not None:
            adapter.close()
        restored = module.restore_original(world=world, bindings=bindings, attempt=attempt)
    if restored is not True:
        raise ValueError('original C111329 world restoration not verified')
    save(attempt / 'native-acquisition.json', packet)
    camera = inventory_camera_sources(packet, attempt)
    (attempt / 'camera-manifest.json').write_text(json.dumps(camera, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    road_bytes = world.get_map().to_opendrive().encode('utf-8')
    publish_original(attempt, packet=packet, camera_manifest=camera, site=site,
                     road_bytes=road_bytes, restoration_verified=True)
    def ref(name):
        path = attempt / name
        return {'path': name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    declaration = {'format': 'c111329-original-source-v1', 'case_id': case_id,
                   'diagnostic_fixture': False, 'site_ref': site_ref,
                   'native_acquisition_ref': ref('native-acquisition.json'),
                   'camera_manifest_ref': ref('camera-manifest.json')}
    (attempt / 'pedestrian-source.json').write_text(json.dumps(declaration, indent=2) + '\n', encoding='utf-8')
    analyze_saved(attempt, attempt / 'analysis-report.json')
    print('sealed original C111329 acquisition: ' + case_id)


if __name__ == '__main__':
    main()
