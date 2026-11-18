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
STATIC_DEVICE_KINDS = frozenset({'traffic_signal','stop_sign','yield_sign',
    'speed_limit_sign','regulatory_sign','lane_control_signal'})
STATIC_KINDS = frozenset({'highway','crosswalk','stop_line','shoulder','sidewalk',
    'intersection','median_or_divider','crest','bicycle_lane_or_path','roadway','centre_line','obstruction'}) | STATIC_DEVICE_KINDS


def validate_kind_inventory(evidence, receipt, kind, claim):
    """Strict additional physical contracts; never an empty-query fallback."""
    import math
    import xml.etree.ElementTree as ET
    contract=receipt.get('kind_inventory_contracts',{}).get(kind)
    if not isinstance(contract,dict):raise ValueError('blocked_missing_inventory_evidence: '+kind)
    sources=receipt['evidence'];proof=contract.get('evidence',{})
    if (contract.get('scope')!='entire_recorded_map' or contract.get('map_sha256')!=receipt['map_sha256']
            or contract.get('constant_during_recording') is not True or not proof
            or 'capture/manifest.json' not in proof or any(sources.get(n)!=h for n,h in proof.items())):
        raise ValueError('Incomplete kind inventory map/scope/source contract: '+kind)
    period=contract.get('time_window_s');rows=evidence.rows('trace.jsonl')
    if (not isinstance(period,list) or len(period)!=2 or not rows
            or any(type(v) not in (int,float) or not math.isfinite(v) for v in period)
            or period[0]>rows[0]['time_s'] or period[1]<rows[-1]['time_s'] or period[0]>period[1]):
        raise ValueError('Kind inventory period does not cover original recording: '+kind)
    if any(type(r.get('time_s')) not in (int,float) or not math.isfinite(r['time_s']) for r in rows) or any(a['time_s']>=b['time_s'] for a,b in zip(rows,rows[1:])):raise ValueError('Invalid original inventory period telemetry')
    instances=contract.get('instances')
    if (not isinstance(instances,list) or len(instances)!=claim['count']
            or any(type(i.get('region')) is not int or i['region']<0 or not isinstance(i.get('kind'),str) for i in instances)
            or len({i['region'] for i in instances})!=len(instances)):
        raise ValueError('Kind inventory instance count/identity mismatch: '+kind)
    if contract.get('unresolved')!=[]:raise ValueError('Unresolved source classification in kind inventory: '+kind)
    if kind in ('roadway','centre_line'):
        if 'road.xodr' not in proof:raise ValueError('Native kind inventory needs bound full map')
        roads=ET.parse(evidence.path('road.xodr')).getroot().findall('road')
        if kind=='roadway':
            if contract.get('method')!='complete_native_roadway_surfaces_v1':raise ValueError('Unknown roadway inventory method')
            expected={int(r.get('id')) for r in roads if r.findall("./lanes/laneSection/left/lane[@type='driving']") or r.findall("./lanes/laneSection/right/lane[@type='driving']")}
            declared=contract.get('native_road_ids',[])
            if any(type(i)is not int for i in declared) or set(declared)!=expected:raise ValueError('Incomplete native roadway scope')
            covered=set()
            for instance in instances:
                ids=instance.get('native_road_ids',[])
                if not ids or any(type(i)is not int for i in ids) or not set(ids)<=expected:raise ValueError('Roadway instance lacks native identity')
                covered.update(ids)
            if covered!=expected:raise ValueError('Unenumerated native roadway surfaces')
        else:
            if contract.get('method')!='complete_opposing_lane_topology_v1':raise ValueError('Unknown centre-line inventory method')
            from .geometry import native_centre_lines,source_lane_direction
            for road in roads:
                for section in road.findall('./lanes/laneSection'):
                    sides=[section.findall("./"+side+"/lane[@type='driving']") for side in ('left','right')]
                    for lanes in sides:
                        values={source_lane_direction(road,lane) for lane in lanes}
                        if None in values or len(values)>1:raise ValueError('Unresolved opposing-lane directions; no zero centre-line claim')
            expected={(o['source']['road_id'],o['source']['section_id']) for o in native_centre_lines(evidence.path('road.xodr'))}
            declared={(i.get('road_id'),i.get('section_id')) for i in instances}
            if declared!=expected:raise ValueError('Centre-line inventory omits geometric opposing divider')
    else:
        if contract.get('method') not in ('complete_physical_objects_v1','audited_closed_world_realization_v1'):raise ValueError('Unknown obstruction inventory method')
        name=contract.get('physical_inventory_source')
        if not isinstance(name,str) or name not in proof or name in ('road.xodr','config.json','capture/manifest.json'):raise ValueError('Obstruction requires original complete physical-object evidence')
        path=evidence.path(name);document=json.loads(path.read_text()) if path else {}
        if (document.get('schema')!='complete-physical-object-inventory-v1' or document.get('map_sha256')!=receipt['map_sha256']
                or document.get('scope')!='entire_recorded_map' or document.get('constant_during_recording')is not True
                or document.get('time_window_s')!=period or document.get('unclassified')!=[]
                or not all(document.get(k)is True for k in ('includes_environment_meshes','includes_static_objects','includes_spawned_despawned_objects'))):
            raise ValueError('Incomplete physical-object environment/time coverage')
        native_frames=[row.get('frame') for row in rows]
        if any(type(frame)is not int or frame<0 for frame in native_frames) or any(a>=b for a,b in zip(native_frames,native_frames[1:])):
            raise ValueError('blocked_missing_inventory_evidence: physical inventory needs ordered original native frame identity')
        execution=document.get('execution',{})
        if (document.get('original_frame_range')!=[rows[0].get('frame'),rows[-1].get('frame')]
                or execution.get('capture_manifest_sha256')!=proof.get('capture/manifest.json')
                or not execution.get('source_hashes')
                or any(proof.get(n)!=h for n,h in execution['source_hashes'].items())
                or not {'runner.py','construction.json'}<=set(execution['source_hashes'])):
            raise ValueError('Physical inventory lacks actual execution/source binding')
        objects=document.get('objects')
        if not isinstance(objects,list) or any(type(o.get('obstruction'))is not bool or not isinstance(o.get('id'),(str,int)) for o in objects):raise ValueError('Unclassified physical object')
        if len({o['id'] for o in objects})!=len(objects):raise ValueError('Duplicate physical object identity')
        expected={o['id'] for o in objects if o['obstruction']}
        if {i.get('object_id') for i in instances}!=expected:raise ValueError('Obstruction classification/instance count mismatch')
        by_id={o['id']:o for o in objects}
        if any(by_id[i['object_id']].get('region')!=i['region'] for i in instances):raise ValueError('Physical obstruction source/region identity differs')


def inventory_kind_facts(receipt):
    """Positive original-kind facts are distinct from complete zero inventory."""
    facts={}
    if receipt:
        for kind,contract in receipt.get('kind_inventory_contracts',{}).items():
            if kind not in receipt.get('kinds',{}):continue
            for instance in contract.get('instances',[]):facts.setdefault(instance['region'],set()).add(instance['kind'])
    return facts


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
    bindings=receipt.get('junction_bindings',[])
    if not isinstance(bindings,list):raise ValueError('Junction bindings must be a list')
    for binding in bindings:
        if (any(type(binding.get(key)) is not int or binding[key]<0 for key in ('region','junction_id','component'))
                or binding.get('map_sha256')!=receipt['map_sha256']
                or not binding.get('evidence')
                or any(sources.get(name)!=digest for name,digest in binding['evidence'].items())):
            raise ValueError('Junction identity requires bound original map/component evidence')
    painted = receipt.get('painted_stop_line_bindings', [])
    if not isinstance(painted, list):
        raise ValueError('Painted stop-line bindings must be a list')
    seen_paint = set()
    for binding in painted:
        key = (binding.get('road_id'), binding.get('object_id'))
        proof = binding.get('evidence', {})
        if (type(key[0]) is not int or not isinstance(key[1], str) or not key[1]
                or key in seen_paint or binding.get('paint_verified') is not True
                or binding.get('reference_verified') is not True
                or not isinstance(binding.get('basis'), str) or not binding['basis']
                or not isinstance(proof, dict) or not proof or not (set(proof)-{'road.xodr'})
                or any(sources.get(name) != digest for name, digest in proof.items())):
            raise ValueError('Painted stop-line estimate needs unique native identity and bound physical paint/reference evidence')
        seen_paint.add(key)
    kinds=receipt.get('kinds',{})
    if not kinds or set(kinds)-STATIC_KINDS:raise ValueError('Unsupported static inventory kind')
    if set(kinds) & STATIC_DEVICE_KINDS and not (set(sources)-{'road.xodr'}):
        raise ValueError('Device inventory requires original acquisition or construction evidence beyond the map')
    for kind,value in kinds.items():
        if (not isinstance(value,dict) or type(value.get('count')) is not int
                or value['count']<0 or not isinstance(value.get('basis'),str) or not value['basis']):
            raise ValueError('Static inventory needs an explicit count and evidence basis: '+kind)
        if kind in ('roadway','centre_line','obstruction'):validate_kind_inventory(evidence,receipt,kind,value)
    return copy.deepcopy(receipt)


def project_static_inventory(scene, receipt, *, refinements=None, verified=None):
    """Remove only uncertainty disproved by a complete, source-bound inventory."""
    if receipt is None:return 0
    changes=0
    for kind,claim in receipt['kinds'].items():
        entities=scene.get('devices' if kind in STATIC_DEVICE_KINDS else 'structures',[])
        if kind in ('roadway','centre_line','obstruction'):
            if refinements is None:raise ValueError('New kind inventory needs pinned Core refinements')
            present=[e for e in entities if kind in refinements.get(e.get('kind'),set())]
            contract=receipt['kind_inventory_contracts'][kind]
            if {e['id'] for e in present}!={i['region'] for i in contract['instances']}:raise ValueError('Static kind instances contradict source inventory')
            if kind!='obstruction':
                for instance in contract['instances']:
                    if not any(instance['kind'] in refinements.get(f,set()) for f in (verified or {}).get(instance['region'],())):raise ValueError('Inventory instance lacks independent native kind binding')
        else:present=[e for e in entities if e.get('kind')==kind]
        if len(present)!=claim['count']:
            raise ValueError('Static '+kind+' inventory contradicts projected instances: '+str((claim['count'],len(present))))
        for entity in entities:
            unknown=entity.get('unobserved_kinds',[])
            if kind in unknown:
                entity['unobserved_kinds']=[k for k in unknown if k!=kind];changes+=1
            if 'unobserved_kinds' in entity and not entity['unobserved_kinds']:
                entity.pop('unobserved_kinds');changes+=1
    return changes



def static_inventory_observations(scene, receipt, frame, atoms, *, refinements=None, verified=None):
    """Project validated whole-recording counts through the same frame receipts."""
    project_static_inventory(scene, receipt,refinements=refinements,verified=verified)
    result = {}
    for kind, claim in receipt['kinds'].items():
        atom = ('dev.' if kind in STATIC_DEVICE_KINDS else 'st.') + kind
        if atom not in atoms:
            continue
        result[atom] = {'status': 'observed_present' if claim['count'] else 'verified_absent',
                        'frame': frame, 'scope': 'entire_recorded_map', 'inventory_complete': True,
                        'method': 'source-bound static inventory', 'map_sha256': receipt['map_sha256']}
    return result


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


def kind_inventory_coverage(scene, receipt):
    """Recording coverage is independent of path capability and positive facts."""
    contracts=(receipt or {}).get('kind_inventory_contracts',{})
    return {kind:({'status':'complete','scope':'entire_recorded_map',
                    'time_window_s':contracts[kind]['time_window_s'],
                    'count':receipt['kinds'][kind]['count'],'method':contracts[kind]['method']}
                  if kind in contracts and kind in (receipt or {}).get('kinds',{}) else
                  {'status':'unknown','scope':'entire_recorded_map',
                   'reason':'blocked_missing_inventory_evidence'})
            for kind in ('roadway','centre_line','obstruction')}
