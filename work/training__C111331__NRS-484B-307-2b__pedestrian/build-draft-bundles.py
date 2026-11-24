"""Build four exact unselected Native construction bundles for pinned offline."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
NATIVE = HERE / 'native'
BASE = HERE.name
SOURCES = ('construction.py', 'runner.py', 'source_join.py', 'road.xodr')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build():
    items = []
    for suffix in ('witness_1', 'witness_2', 'exception_1_1', 'exception_1_2'):
        case_id = BASE + '__' + suffix
        contrary = suffix in ('witness_2', 'exception_1_2')
        config = {
            'case_id': case_id, 'selected_case_id': case_id,
            'case_suffix': suffix, 'cell_id': 'C111331',
            'law_id': 'NRS-484B-307-2b', 'actor': 'pedestrian',
            'duration_s': 30, 'rate_hz': 20,
            'cameras': [{'name': n, 'width': w, 'height': h} for n, w, h in (
                ('overview', 1920, 1080), ('approach', 1280, 720),
                ('reference_corner', 1280, 720), ('driver_reference', 1280, 720))],
            'requested_pedestrian_indication': 'dont_walk' if contrary else 'walk',
            'traffic_head_id': 'C111331-facing-circular-head',
            'pedestrian_head_id': 'C111331-governing-pedestrian-head',
            'required_atoms': ['ru.pedestrian', 'kin.position', 'st.crosswalk', 'rel.occupies'],
            'source_packets': [], 'case': {'case_id': case_id},
        }
        files = [{'path': source, 'content': (NATIVE / source).read_text()}
                 for source in SOURCES]
        files.append({'path': 'tests/test_construction.py',
                      'content': (NATIVE / 'tests/test_construction.py').read_text()})
        files.append({'path': 'config.json', 'content': json.dumps(config, indent=2) + '\n'})
        construction = {'case_id': case_id, 'cell_id': 'C111331',
                        'law_id': 'NRS-484B-307-2b', 'actor': 'pedestrian',
                        'entrypoint': 'runner.py', 'files': files,
                        'recording_description': {'channels': [
                            {'name': 'pedestrian pose', 'source': 'Native walker transform'},
                            {'name': 'signal devices', 'source': 'Native light readback and original camera pixels'},
                            {'name': 'crosswalk', 'source': 'authored map and Native map readback'}],
                            'limitations': ['Physical signal visibility and governance unverified',
                                            'No legal verdict from requested indication']},
                        'status': 'unselected_cpu_draft'}
        path = HERE / 'draft-native-bundles' / suffix / 'construction.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(construction, indent=2) + '\n')
        items.append({'case_id': case_id, 'kind': 'draft_not_selected',
                      'construction': str(path.relative_to(HERE)),
                      'construction_sha256': sha(path), 'candidates': [],
                      'candidate_risk': {'status': 'physical',
                          'reason': 'Signal pixels, governance and crossing may fail on Native map'}})
    manifest = {'format': 'worker-unselected-draft-construction-manifest-v1',
                'assignment_id': BASE, 'status': 'draft_not_selected', 'cases': items}
    path = HERE / 'draft-native-execution-manifest.json'
    path.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'cases': len(items), 'manifest_sha256': sha(path)}, sort_keys=True))


if __name__ == '__main__':
    build()
