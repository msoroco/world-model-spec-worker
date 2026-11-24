"""Verify explicitly authored legal contexts over one retained physical episode.

This lineage is neither a recapture nor a same-case source amendment. Parent
physical staging may be validated without an accepted parent legal outcome.
"""
import copy
import json
import re
from functools import lru_cache
from itertools import zip_longest
from pathlib import Path

from context_catalogue import declared_assumptions
from recording_store import identity, sha
from trace_json import scenes
from traffic_spec_adapter.atom_contract import common_profile_complete

FORMAT = 'offline-legal-context-variant-v1'
ATOM = 'asm.way_within_business_or_residential_district'


def _check(condition, message):
    if not condition:raise ValueError('Invalid legal-context variant: '+message)


def _bound(reference):
    _check(isinstance(reference, dict) and set(reference) == {'path', 'sha256'}, 'unbound artifact')
    path = Path(reference['path'])
    _check(path.is_absolute() and path.is_file() and sha(path) == reference['sha256'], 'artifact changed: '+str(path))
    return path


def recording_id(source_id, definition_hash, trace_hash, manifest_hash, video_hash, core_hash):
    values = [source_id, definition_hash, trace_hash, manifest_hash, video_hash, core_hash]
    _check(all(isinstance(v, str) and re.fullmatch('[0-9a-f]{64}', v) for v in values), 'identity hashes')
    return identity([FORMAT]+values)


def metadata_binding(receipt_path):
    path = Path(receipt_path).resolve()
    return {'format': FORMAT, 'receipt': {'path': str(path), 'sha256': sha(path)}}


def _encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


@lru_cache(maxsize=16)
def _physical_proof(source_path, target_path, source_hash, target_hash, value, frames):
    count = 0;first_t = last_t = None
    for source, target in zip_longest(scenes(source_path), scenes(target_path)):
        _check(source is not None and target is not None, 'frame count changed')
        old, _ = source;new, _ = target;expected = dict(old)
        declarations = [p for p in old.get('assumptions', []) if p[0] == ATOM]
        _check(len(declarations) == 1 and type(declarations[0][1]) is bool, 'source district declaration')
        expected['assumptions'] = [[name, value if name == ATOM else flag]
                                   for name, flag in old['assumptions']]
        _check(_encoded(new) == _encoded(expected), 'unrelated scene or undeclared context changed')
        first_t = old['t'] if count == 0 else first_t;last_t = old['t']
        count += 1
    _check(count == frames, 'receipt frame count')
    return first_t, last_t


def _core(reference, trace, manifest, frames, executable):
    record = json.loads(_bound(reference).read_text())
    _check(record.get('returncode') == 0, 'Core did not pass')
    _check(record.get('trace', {}).get('sha256') == trace['sha256'] and
           record.get('manifest', {}).get('sha256') == manifest['sha256'], 'Core input binding')
    _check(_bound(record['executable']).resolve() == executable.resolve(), 'current Core executable')
    output = _bound(record['stdout']).read_text()
    decoded = re.search(r'\bdecoded_frames=(\d+)\b', output)
    _check(decoded is not None and int(decoded.group(1)) == frames, 'Core frame count')
    _check(re.search(r'\bfull_core=true\b', output) is not None and
           re.search(r'\bintentions_only=false\b', output) is not None, 'Core is not the full contract')
    return record


def verify_legal_context_variant(folder, metadata, root):
    """Verify a typed metadata binding and every physical frame without writes.

    ``root`` supplies the trusted original recording registry and current Core;
    ``folder`` may be external canonical-shaped staging named by its new ID.
    Absolute, hash-bound receipts can retain original external source archives.
    """
    folder = Path(folder);root = Path(root)
    binding = metadata.get('legal_context_variant', {})
    _check(set(binding) == {'format', 'receipt'} and binding.get('format') == FORMAT and
           not metadata.get('recapture'), 'lineage type')
    receipt = json.loads(_bound(binding.get('receipt')).read_text())
    _check(receipt.get('format') == FORMAT and receipt.get('new_capture') is False, 'not a new capture')
    rid = receipt.get('recording_id');source_id = receipt.get('source_recording_id')
    _check(rid == folder.name == metadata.get('recording_id') and rid != source_id, 'recording identity')
    source = receipt['source'];target = receipt['target'];frames = receipt['frames']
    _check(type(frames) is int and frames > 0, 'frame count')
    for name in ('definition', 'trace', 'manifest', 'profile', 'selector', 'Core', 'video'):_bound(source[name])
    for name in ('definition', 'trace', 'manifest', 'Core', 'video'):_bound(target[name])
    for name, field in [('trace', 'trace_sha256'), ('manifest', 'manifest_sha256'), ('video', 'video_sha256')]:
        _check(sha(folder/(name+'.json' if name != 'video' else 'video.webm')) == target[name]['sha256'] == metadata.get(field), 'target '+name)
    _check(source['video']['sha256'] == target['video']['sha256'], 'physical video changed')
    old = json.loads(_bound(source['definition']).read_text());new = json.loads(_bound(target['definition']).read_text())
    _check(new['case_id'] == metadata.get('case_id') == receipt.get('case_id') and old['case_id'] != new['case_id'], 'case identity')
    _check(old['target_law_id'] == new['target_law_id'] == metadata.get('law_id'), 'law changed')
    selector = json.loads(_bound(source['selector']).read_text())
    _check(selector.get('recording_id') == source_id and selector.get('case_id') == old['case_id'], 'parent identity')
    for name, key in [('trace', 'trace'), ('manifest', 'manifest'), ('profile', 'current_profile'), ('Core', 'Core')]:
        _check(selector[key]['sha256'] == source[name]['sha256'], 'parent '+name)
    profile = json.loads(_bound(source['profile']).read_text())
    _check(common_profile_complete(profile) and profile.get('required_field_gaps') == {} and
           profile.get('processing_limits') == {}, 'parent measurements incomplete')
    original_id = receipt['original_source_recording_id']
    _check(isinstance(original_id, str) and re.fullmatch('[0-9a-f]{64}', original_id), 'original source identity')
    raw_definition = root/'recordings'/original_id/'evidence/expected_label_case_definition.json'
    _check(raw_definition.is_file() and sha(raw_definition) == source['definition']['sha256'], 'original capture definition')
    author = json.loads(_bound(receipt['author_request']).read_text())
    _check(author.get('type') == 'user_authorized_new_legal_context_variants' and
           author.get('original_recording_id') == source_id and author.get('scope') == 'whole_episode' and
           author.get('physical_capture_changes_authorized') is False, 'author scope')
    flag = receipt['context']['value']
    _check(set(receipt['context']) == {'atom', 'value'} and
           receipt['context'].get('atom') == ATOM and type(flag) is bool, 'context declaration')
    district = 'business_or_residential' if flag else 'other_area'
    _check(any(c.get('district') == district and c.get('minimum_ft') == (100 if flag else 300)
               and (flag or c.get('neither_business_nor_residential') is True) for c in author['contexts']), 'unauthorized district')
    context = new['authored_test_context']
    _check(set(context) == {'district', 'scope', 'provenance', 'scene_assumptions',
                           'manual_signaling_intended', 'manual_signaling_scope_authority'} and
           context.get('district') == district and context.get('scope') == 'whole_episode' and
           declared_assumptions(context) == [[ATOM, flag]], 'definition context')
    _check(set(context['scene_assumptions']) == {'district'}, 'extra physical context')
    scene_district = context['scene_assumptions']['district']
    district_keys = {'classification', 'external_authored_assumption', 'scope', 'provenance'}
    if not flag:district_keys.add('neither_business_nor_residential')
    _check(set(scene_district) == district_keys and scene_district.get('classification') == district and
           scene_district.get('external_authored_assumption') is True and
           scene_district.get('scope') == 'whole_episode' and
           isinstance(context['provenance'], str) and bool(context['provenance'].strip()) and
           scene_district.get('provenance') == context['provenance'] and
           (flag or scene_district.get('neither_business_nor_residential') is True), 'district context semantics')
    manual = json.loads(_bound(receipt['no_manual_signaling_authority']).read_text())
    _check(manual.get('manual_signaling_intended') is False and
           manual.get('scope') == 'Entire authored episode for each listed recording' and
           any(r.get('current_recording_id') == source_id and r.get('case_id') == old['case_id'] for r in manual['recordings']), 'manual-signaling authority')
    authority = context['manual_signaling_scope_authority']
    _check(context.get('manual_signaling_intended') is False and
           set(authority) == {'receipt', 'type', 'same_physical_episode', 'observed_hand_state_claimed'} and
           authority['receipt'] == receipt['no_manual_signaling_authority'] and
           authority.get('type') == 'author_confirmed_original_episode_intent' and
           authority.get('same_physical_episode') is True and
           authority.get('observed_hand_state_claimed') is False, 'unobserved hand status')
    semantic = {'case_id', 'paired_probe_id', 'authored_test_context', 'deliberate_differences', 'rationale',
                'unresolved_judgment_calls', 'probe', 'expected_label_specification', 'source_definition_preserved',
                'source_unresolved_inputs', 'execution_readiness', 'variable_assignments'}
    _check(_encoded({k:v for k,v in old.items() if k not in semantic}) ==
           _encoded({k:v for k,v in new.items() if k not in semantic}), 'physical definition changed')
    assignments = copy.deepcopy(new['variable_assignments'])
    assignments['approach_location_and_land_use']['value']['legal_region_classification'] = old['variable_assignments']['approach_location_and_land_use']['value']['legal_region_classification']
    _check(_encoded(assignments) == _encoded(old['variable_assignments']), 'requested physical settings changed')
    specification = new['expected_label_specification']
    _check(set(specification) == {'intended_outcome', 'scope', 'core_assumptions', 'scene_assumptions',
                                 'author_request', 'not_a_recorded_verdict'} and
           specification['core_assumptions'] == [[ATOM, flag]] and
           specification['scene_assumptions'] == context['scene_assumptions'] and
           specification['not_a_recorded_verdict'] is True and
           specification['author_request'] == receipt['author_request'], 'authored definition binding')
    preserved = new['source_definition_preserved']
    _check(_bound({k:preserved[k] for k in ('path','sha256')}) and
           preserved['sha256'] == source['definition']['sha256'] and
           preserved.get('original_recording_id') == source_id and preserved.get('original_case_id') == old['case_id'], 'preserved source definition')
    source_manifest = json.loads(_bound(source['manifest']).read_text())
    target_manifest = json.loads(_bound(target['manifest']).read_text())
    manifest_declaration = target_manifest.pop('authored_legal_context_variant', None)
    _check(_encoded(source_manifest) == _encoded(target_manifest), 'physical capabilities changed')
    _check(isinstance(manifest_declaration, dict) and manifest_declaration.get('author_request') == receipt['author_request'] and
           manifest_declaration.get('definition') == target['definition'] and
           manifest_declaration.get('reading_assumptions') == [[ATOM, flag]] and
           manifest_declaration.get('same_physical_episode') == source_id and
           json.loads(_bound(manifest_declaration['context']).read_text()) == context, 'manifest context binding')
    executable = root/'inputs/shared/tools/adapterCheck'
    _core(source['Core'], source['trace'], source['manifest'], frames, executable)
    current = _core(target['Core'], target['trace'], target['manifest'], frames, executable)
    expected_id = recording_id(source_id, target['definition']['sha256'], target['trace']['sha256'],
                               target['manifest']['sha256'], target['video']['sha256'], current['executable']['sha256'])
    _check(rid == expected_id, 'identity formula')
    start_t, end_t = _physical_proof(str(_bound(source['trace'])), str(_bound(target['trace'])),
                                   source['trace']['sha256'], target['trace']['sha256'], flag, frames)
    scope = manifest_declaration['scope']
    _check(scope.get('start_scene') == 0 and scope.get('end_scene') == frames-1 and
           scope.get('start_t') == start_t and scope.get('end_t') == end_t, 'manifest context window')
    return receipt
