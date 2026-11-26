"""Bind completed exact-case CPU construction without asserting physical acceptance."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def main():
    draft = json.loads((HERE / 'draft-bridge-manifest.json').read_text())
    first = json.loads((HERE / draft['cases'][0]['construction']).read_text())
    for item in first['files']:
        target = HERE / item['path']
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(item['content'])
    write(HERE / 'construction.json', first)
    plan = json.loads((HERE / 'case-plan.json').read_text())
    plan['camera_plan'] = {'profile': 'overview1080-capability', 'duration_s': 30,
                           'composition': 'synchronized_four_view_primary',
                           'coverage': [
                               {'view': 'overview', 'subject': 'qualifying elevated bridge mesh, both approaches and vehicle', 'interval': 'all 600 original frames; physical sight lines unverified'},
                               {'view': 'approach', 'subject': 'near 100-foot structural maximum sign and entering vehicle', 'interval': 'approach through deck entry'},
                               {'view': 'reference_corner', 'subject': 'far sign and outgoing bridge end', 'interval': 'deck occupancy through exit'},
                               {'view': 'driver_reference', 'subject': 'driver and vehicle travel over structure', 'interval': 'all 600 original frames'}]}
    plan['source_observation_mapping'] = {
        'st.elevated_structure': {'evidence': 'Native road/elevation readback, OpenDRIVE and original camera pixels; rendered bridge qualification still unverified',
                                  'channels': ['structure_sign_survey'], 'source_refs': ['road.xodr', 'bridge-context.json']},
        'dev.speed_limit_sign': {'evidence': 'Two native sign metadata rows and later independently reviewed sign-face pixels',
                                 'channels': ['structure_sign_survey'], 'source_refs': ['bridge-context.json', 'pixel-review.json']},
        'dev.position': {'evidence': 'Native sign road coordinate and distance to each bridge end',
                         'channels': ['structure_sign_survey'], 'source_refs': ['bridge-context.json']},
        'dev.governs': {'evidence': 'Native sign orientation and approach road/lane; governance requires later physical review',
                        'channels': ['structure_sign_survey'], 'source_refs': ['road.xodr', 'bridge-context.json']},
        'kin.speed': {'evidence': 'Original post-tick velocity vector on deck, joined to frame map',
                      'channels': ['original_velocity_position'], 'source_refs': ['bridge-speed-history.jsonl']},
        'rel.occupies': {'evidence': 'Original vehicle position and elevated deck interval; physical mesh remains unverified',
                         'channels': ['original_velocity_position', 'structure_sign_survey'], 'source_refs': ['bridge-speed-history.jsonl', 'bridge-context.json']},
        'drv.approaching': {'evidence': 'Original vehicle trajectory in governed approach lane',
                            'channels': ['original_velocity_position', 'structure_sign_survey'], 'source_refs': ['bridge-speed-history.jsonl', 'road.xodr']}}
    plan['observations'] = [
        {'name': 'original_velocity_position', 'mandatory': True, 'reason': 'original actor position and velocity for on-structure speed'},
        {'name': 'structure_sign_survey', 'mandatory': True, 'reason': 'original bridge and sign readback for both approaches'}]
    for item in plan['cases']:
        item['kind'] = 'delivery'
        item['selection_status'] = 'selected_cpu_proof_pending_independent_delivery_review'
        item['construction_status'] = 'current_runtime_offline_and_public_compatibility_passed_physical_unverified'
        suffix = item['case_id'].rsplit('__', 1)[-1]
        entry = next(e for e in draft['cases'] if e['case_id'] == item['case_id'])
        item['construction'] = entry['construction']
        item['construction_sha256'] = entry['construction_sha256']
    write(HERE / 'case-plan.json', plan)
    manifest = {'format': 'worker-execution-manifest', 'assignment_id': HERE.name,
                'runtime_manifest_sha256': draft['runtime_manifest_sha256'],
                'status': 'partial', 'cases': draft['cases']}
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        source = HERE / 'proof' / suffix / 'primary'
        entry['physical_preparation'] = {
            'receipt': f'proof/{suffix}/physical-preparation.json',
            'sha256': sha(HERE / 'proof' / suffix / 'physical-preparation.json')}
        entry['compatibility'] = dict(entry['compatibility'])
        entry['negative'] = {'log': entry['compatibility']['negative_log']}
        entry['native_handoff'] = {'python_env_var': 'CARLA_PYTHON',
                                   'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'}
        entry['acquisition'] = {
            'original_velocity_position': {'entrypoint': 'finalize.py',
                                            'method': 'original 600-frame bridge history and FrameMap join',
                                            'evidence': 'bridge-speed-history.jsonl; video_frames.jsonl; channels/original_velocity_position.jsonl'},
            'structure_sign_survey': {'entrypoint': 'finalize.py',
                                      'method': 'native bridge road/sign survey carried through source-bound saved finalization',
                                      'evidence': 'road.xodr; bridge-context.json; channels/structure_sign_survey.jsonl'}}
        entry['delivery_readiness'] = 'pending_independent_delivery_and_saved_processing_proofs'
    write(HERE / 'execution-manifest.json', manifest)
    print(json.dumps({'case_count': len(manifest['cases']),
                      'manifest_sha256': sha(HERE / 'execution-manifest.json')}))


if __name__ == '__main__':
    main()
