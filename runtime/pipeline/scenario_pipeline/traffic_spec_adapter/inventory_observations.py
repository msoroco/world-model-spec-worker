"""Evidence-backed object inventories: presence, verified absence, or unknown.

Absence needs either a complete original observation or a hash-bound static
inventory justified by the retained acquisition and construction. A native-map
empty list, configuration, or requested scene alone is never enough. Legacy
captures do not acquire renderer coverage retrospectively by changing a flag.
"""
import hashlib
import copy
import json
from pathlib import Path

SCHEMA = 'scene-inventory-observation-v1'
# Extend only after specifying each family's physical inventory contract.
SUPPORTED_ATOMS = {'st.crosswalk': ('crosswalk', 'structures')}
STATIC_KINDS = frozenset({'highway','crosswalk','stop_line','shoulder','sidewalk',
    'intersection','median_or_divider','crest','bicycle_lane_or_path','lane_control_signal'})


def retained_static_inventory(evidence, receipt=None):
    """Validate an offline interpretation of the original static construction.

    This is a derived receipt, never an invented original observation packet.
    Its evidence hashes and map identity must still match the retained capture.
    Counts describe a complete inventory, not a default for missing measurements.
    """
    if receipt is None:
        candidate=evidence.base/'static_map_inventory.json'
        if not candidate.exists():return None
        path=evidence.path('static_map_inventory.json')
        if path is None:raise ValueError('Static map inventory must be bound to the closed original capture')
        receipt=json.loads(path.read_text())
    if (receipt.get('schema')!='retained-static-inventory-v1'
            or receipt.get('scope')!='entire_recorded_map'
            or receipt.get('constant_during_recording') is not True):
        raise ValueError('Static inventory requires a complete, constant recorded-map scope')
    sources=receipt.get('evidence',{})
    if not sources or 'road.xodr' not in sources:
        raise ValueError('Static inventory needs original map and acquisition evidence')
    for name,digest in sources.items():
        if (Path(name).is_absolute() or '..' in Path(name).parts or name.startswith('traffic_spec/')
                or evidence.path(name) is None or evidence.used.get(name)!=digest):
            raise ValueError('Static inventory source differs from original evidence: '+name)
    if receipt.get('map_sha256')!=sources['road.xodr']:
        raise ValueError('Static inventory belongs to another map')
    declaration=receipt.get('authored_road_access')
    if declaration is not None:
        from context_catalogue import public_road_ids
        config_path=evidence.path('config.json')
        config=json.loads(config_path.read_text()) if config_path else {}
        public=set(public_road_ids(evidence.path('road.xodr'),config,declaration,receipt['map_sha256']))
        grouped=set()
        for group in declaration.get('way_groups',[]):
            roads=group.get('roads',[]);primary=group.get('parallel_carriageways',[]);proof=group.get('evidence',{})
            if (not roads or any(type(i)is not int for i in roads)or not set(roads)<=public or grouped&set(roads)
                    or group.get('kind')!='verified_divided_road_layout' or len(primary)<2 or not set(primary)<=set(roads)
                    or not proof or any(sources.get(name)!=digest for name,digest in proof.items())):
                raise ValueError('Way identity needs non-overlapping public native roads and bound original design evidence')
            grouped.update(roads)
        bindings=receipt.get('highway_bindings',[])
        if not isinstance(bindings,list):raise ValueError('Highway bindings must be a list of native identities')
        seen=set()
        for binding in bindings:
            ident=binding.get('region');roads=binding.get('roads')
            if (type(ident)is not int or ident<0 or ident in seen or not isinstance(roads,list)
                    or not roads or any(type(i)is not int for i in roads)or not set(roads)<=public):
                raise ValueError('Highway binding contradicts native public-road identities')
            seen.add(ident)
    kinds=receipt.get('kinds',{})
    if not kinds or set(kinds)-STATIC_KINDS:raise ValueError('Unsupported static inventory kind')
    for kind,value in kinds.items():
        if (not isinstance(value,dict) or type(value.get('count')) is not int
                or value['count']<0 or not isinstance(value.get('basis'),str) or not value['basis']):
            raise ValueError('Static inventory needs an explicit count and evidence basis: '+kind)
    return copy.deepcopy(receipt)


def project_static_inventory(scene, receipt):
    """Remove only uncertainty disproved by a complete, source-bound inventory."""
    if receipt is None:return 0
    changes=0
    for kind,claim in receipt['kinds'].items():
        entities=scene.get('devices' if kind=='lane_control_signal' else 'structures',[])
        present=[e for e in entities if e.get('kind')==kind]
        if len(present)!=claim['count']:
            raise ValueError('Static '+kind+' inventory contradicts projected instances: '+str((claim['count'],len(present))))
        for entity in entities:
            unknown=entity.get('unobserved_kinds',[])
            if kind in unknown:
                entity['unobserved_kinds']=[k for k in unknown if k!=kind];changes+=1
            if 'unobserved_kinds' in entity and not entity['unobserved_kinds']:
                entity.pop('unobserved_kinds');changes+=1
    return changes


def complete_generated_lanes(manifest, native_facts, map_hash):
    """Closed native lane topology/paint, not a renderer or legal-role inventory."""
    return (isinstance(map_hash,str) and len(map_hash)==64
            and manifest.get('map')=='Carla/Maps/OpenDriveMap'
            and native_facts.get('map')==manifest['map']
            and manifest.get('complete_driving_lanes') is True
            and manifest.get('sources',{}).get('road.xodr')==map_hash)


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


class Evidence:
    """Read only retained files whose original integrity can be checked."""
    def __init__(self, recording):
        recording = Path(recording)
        self.recording = recording
        self.base = recording / 'evidence'
        path = recording/'evidence-checksums.json'
        self.expected = json.loads(path.read_text()) if path.exists() else {}
        self.used = {}
        self.problems = []
        self.closed = False
        self._paths = {}
        if not self.expected and (self.base/'result.json').is_file():
            # Derived exports can legitimately change after capture. Bind each
            # raw file to the original atomic receipt rather than re-verifying
            # every derived trace, video and graph before reading one map.
            value=json.loads((self.base/'result.json').read_text())
            completion=value.get('completion',{})
            body={k:v for k,v in value.items() if k!='completion'}
            digest=hashlib.sha256(json.dumps(body,sort_keys=True,allow_nan=False).encode()).hexdigest()
            hashes=completion.get('artifact_hashes',{})
            if hashes and digest==completion.get('result_hash') and completion.get('binding'):
                self.expected={'evidence/'+name:expected for name,expected in hashes.items()}
                self.used['result.json']=sha(self.base/'result.json')
            else:
                self.problems.append('Original per-file completion hashes unavailable or result body changed')

    def path(self, name):
        if name in self._paths:
            return self._paths[name]
        path = self.base/name
        if not path.is_file():
            return None
        digest = sha(path)
        expected = self.expected.get('evidence/' + name)
        # A hash-bound capture manifest transitively binds its original source
        # files and native-map facts. Older checksum inventories may omit them.
        capture=self.base/'capture/manifest.json'
        capture_hash=self.expected.get('evidence/capture/manifest.json')
        if expected is None and capture_hash and capture.is_file() and sha(capture)==capture_hash:
            manifest=json.loads(capture.read_text())
            expected=manifest.get('sources',{}).get(name)
            facts=manifest.get('native_map_facts',{})
            if name=='capture/'+facts.get('path',''):expected=facts.get('sha256')
        if expected is not None and digest != expected:
            raise ValueError('Retained evidence checksum mismatch: ' + str(path))
        if expected is None and not self.closed:
            self.problems.append('No original hash binding for ' + name)
            return None
        self.used[name] = digest
        self._paths[name] = path
        return path

    def rows(self, name):
        path = self.path(name)
        if path is None:
            return []
        with path.open() as stream:
            return [json.loads(line) for line in stream if line.strip()]
