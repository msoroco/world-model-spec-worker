"""Evidence-backed object inventories: presence, verified absence, or unknown.

Only original, frame-bound inventory observations can establish absence. A
native-map empty list, configuration, or requested scene is never a receipt.
Full renderer/region inventory acquisition is an explicit producer contract;
legacy captures do not acquire it retrospectively by changing a flag.
"""
import hashlib
import json
from pathlib import Path

SCHEMA = 'scene-inventory-observation-v1'
# Extend only after specifying each family's physical inventory contract.
SUPPORTED_ATOMS = {'st.crosswalk': ('crosswalk', 'structures')}


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def evidence_file(original, reference):
    if not isinstance(reference, dict) or not isinstance(reference.get('path'), str):
        raise ValueError('Inventory evidence requires an explicit source file')
    path = (original / reference['path']).resolve()
    if original not in path.parents or not path.is_file():
        raise ValueError('Inventory evidence escapes or is missing from the original attempt')
    expected = reference.get('sha256')
    if not isinstance(expected, str) or len(expected) != 64 or sha(path) != expected:
        raise ValueError('Inventory evidence source hash mismatch')
    return path


def complete_inventory(original, reference, source_kind, frame, map_hash):
    path = evidence_file(original, reference)
    value = json.loads(path.read_text())
    if (value.get('schema') != 'complete-scene-inventory-v1'
            or value.get('source_kind') != source_kind
            or value.get('frame') != frame
            or value.get('map_sha256') != map_hash
            or value.get('scope') != 'entire_recorded_scene'
            or value.get('coverage_complete') is not True):
        raise ValueError('Inventory does not establish complete same-frame scene coverage')
    if not isinstance(value.get('observations'), list) or value.get('unclassified') != []:
        raise ValueError('Inventory contains unclassified or unavailable scene objects')
    if any(not isinstance(item, dict) or item.get('crosswalk_classification') not in ('crosswalk', 'not_crosswalk') for item in value['observations']):
        raise ValueError('Every inventoried object needs an observed crosswalk classification')
    if any(item['crosswalk_classification'] == 'crosswalk' for item in value['observations']):
        raise ValueError('Absence contradicts a classified crosswalk object')
    if value.get('crosswalk_regions') != []:
        raise ValueError('An absence receipt contradicts observed crosswalk regions')
    if source_kind == 'renderer_scene_inventory':
        if not all(value.get(k) is True for k in ('includes_decals', 'includes_material_markings')):
            raise ValueError('Renderer inventory does not cover decals and material markings')
    elif source_kind == 'crosswalk_region_inventory':
        if not all(value.get(k) is True for k in ('includes_marked_regions', 'includes_unmarked_regions')):
            raise ValueError('Region inventory does not cover marked and unmarked crosswalks')
    return {'path': str(path), 'sha256': reference['sha256'], 'source_kind': source_kind}


def verify_absence(original, packet, row, native_facts, map_hash):
    if (packet.get('schema') != SCHEMA or packet.get('atom') != 'st.crosswalk'
            or packet.get('frame') != row['frame']
            or packet.get('scope') != 'entire_recorded_scene'
            or packet.get('map_sha256') != map_hash):
        raise ValueError('Absence receipt has the wrong frame, map, atom, or scope')
    # This packet must be inside original trace.jsonl, already hash-bound by the
    # closed capture manifest and executor completion, not a mutable config flag.
    if native_facts.get('crosswalk_vertices_m') != []:
        raise ValueError('Absence needs an observed empty native crosswalk inventory')
    source = evidence_file(original, packet.get('instrumentation'))
    construction = json.loads((original / 'construction.json').read_text())
    files = {f['path']: f['content'] for f in construction.get('files', [])}
    name = str(source.relative_to(original))
    if name not in files or hashlib.sha256(files[name].encode()).hexdigest() != sha(source):
        raise ValueError('Inventory instrumentation is not bound to the executed construction')
    refs = [complete_inventory(original, packet.get('rendered_markings'),
                               'renderer_scene_inventory', row['frame'], map_hash),
            complete_inventory(original, packet.get('crosswalk_regions'),
                               'crosswalk_region_inventory', row['frame'], map_hash)]
    return {'status': 'verified_absent', 'frame': row['frame'], 'map_sha256': map_hash,
            'instrumentation': {'path': str(source), 'sha256': sha(source)},
            'evidence_sources': refs, 'scope': 'entire_recorded_scene'}


def observations(original, telemetry, native_facts, required):
    original = Path(original).resolve()
    map_hash = sha(original / 'road.xodr')
    result = {}
    for atom in sorted(set(required) & set(SUPPORTED_ATOMS)):
        values = []
        for row in telemetry:
            packets = row.get('inventory_observations', {})
            if not isinstance(packets, dict):
                raise ValueError('Original inventory observations must be keyed by canonical atom')
            packet = packets.get(atom)
            if packet is None:
                values.append({'status': 'unknown', 'frame': row['frame'],
                               'reason': 'No original complete renderer and region inventory receipt; native-map emptiness is insufficient'})
            elif not isinstance(packet, dict):
                raise ValueError('Invalid original inventory observation')
            else:
                values.append(verify_absence(original, packet, row, native_facts, map_hash))
        result[atom] = values
    return result


def project(scene, inventory, index):
    """Use existing Core uncertainty fields; do not fabricate placeholder regions."""
    frame = {}
    for atom, values in inventory.items():
        from .native_control_observations import ATOMS, project as project_native
        if atom in ATOMS:
            frame[atom] = project_native(scene, atom, values[index])
            continue
        kind, domain = SUPPORTED_ATOMS[atom]
        record = dict(values[index])
        entities = scene.get(domain, [])
        present = [e for e in entities if e.get('kind') == kind
                   and kind not in e.get('unobserved_kinds', [])]
        if record['status'] == 'verified_absent':
            if present:
                raise ValueError('Verified absence contradicts a mapped crosswalk entity')
            # An independently complete empty inventory makes this kind known
            # absent. No geometry, occupancy, or unrelated kind is modified.
            for entity in entities:
                if kind in entity.get('unobserved_kinds', []):
                    entity['unobserved_kinds'] = [k for k in entity['unobserved_kinds'] if k != kind]
        else:
            # Presence is supported for each observed object. Classification of
            # missing crosswalk regions is unknown, never silently false.
            for entity in entities:
                if entity.get('kind') != kind:
                    entity['unobserved_kinds'] = sorted(set(entity.get('unobserved_kinds', [])) | {kind})
            if present:
                record.update(status='observed_present', observed_entity_ids=[e['id'] for e in present],
                              inventory_complete=False)
        frame[atom] = record
    return frame
