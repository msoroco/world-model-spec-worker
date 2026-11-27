"""Read an exception request and its independently retained source packet.

A requested context is a comparison input. It is never a finding that the
statutory exception applies to the observed driver.
"""

import hashlib
import json
from pathlib import Path


BRANCHES = ('traffic_conflict', 'other_law', 'police_direction', 'official_device')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_context(path, case_id, capture_seal=None):
    path = Path(path)
    if not path.is_file():
        raise ValueError('Missing required source: exception-context.json')
    record = json.loads(path.read_text())
    suffix = case_id.split('__')[-1]
    branch = next((name for name in BRANCHES if suffix.startswith(name + '_')), None)
    if branch is None or suffix not in tuple(name + '_' + str(i) for name in BRANCHES for i in (1, 2)):
        raise ValueError('Unknown exact rail exception case')
    expected = suffix.endswith('_2')
    if (record.get('case_id') != case_id or record.get('branch') != branch or
            record.get('requested_context_present') is not expected or
            record.get('activity_request') != 'park' or
            record.get('source_kind') not in ('synthetic_cpu', 'reviewed_authority_context') or
            record.get('legal_applicability_claimed') is not False):
        raise ValueError('Exception source or selected comparison target differs')
    if capture_seal is not None:
        seal = json.loads(Path(capture_seal).read_text())
        if seal.get('sources', {}).get('exception-context.json') != sha(path):
            raise ValueError('Exception context changed after capture seal')
        diagnostic = seal.get('diagnostic_fixture') is True
        if diagnostic != (record['source_kind'] == 'synthetic_cpu'):
            raise ValueError('Exception context provenance differs from capture')
    sources = record.get('sources')
    if not isinstance(sources, dict):
        raise ValueError('Exception context source inventory missing')
    if record['source_kind'] == 'reviewed_authority_context' and not sources:
        raise ValueError('Reviewed exception context needs original source hashes')
    for name, source in sources.items():
        if not isinstance(name, str) or not isinstance(source, dict):
            raise ValueError('Invalid exception source entry')
        relative = Path(source.get('path', ''))
        if (not relative.parts or relative.is_absolute() or '..' in relative.parts or
                not source.get('sha256') or not source.get('citation')):
            raise ValueError('Exception source needs a relative path, hash and citation')
        cited = (path.parent / relative).resolve()
        if path.parent.resolve() not in cited.parents or not cited.is_file() or sha(cited) != source['sha256']:
            raise ValueError('Original exception source missing or changed: ' + name)
    return record
