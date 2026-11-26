"""Negative source-binding tests without an authority or legal verdict."""
import hashlib
import json
from pathlib import Path
import tempfile

from authority_source import ASSIGNMENT, check


def run():
    with tempfile.TemporaryDirectory(prefix='c229977-authority-', dir='.runtime-work') as name:
        root = Path(name)
        sources = {}
        for filename in ('vehicle-trace.jsonl', 'video_frames.jsonl',
                         'authority-context.json', 'device-trace.jsonl'):
            path = root / filename
            path.write_text('{}\n')
            sources[filename] = hashlib.sha256(path.read_bytes()).hexdigest()
        cases = []
        for kind in ('governing_law', 'official_device'):
            for state in ('absent', 'present'):
                case = ASSIGNMENT + '__' + kind + '_' + state
                binding = None
                if state == 'present' and kind == 'governing_law':
                    law = root / 'specific-law.txt'
                    law.write_text('Synthetic source shape only; no authority asserted.\n')
                    binding = {'law_citation': 'synthetic-test',
                               'law_text_source': law.name,
                               'law_text_sha256': hashlib.sha256(law.read_bytes()).hexdigest(),
                               'scope_review': 'synthetic-test'}
                elif state == 'present':
                    binding = {'device_actor_id': 42,
                               'official_status_source': 'device-trace.jsonl',
                               'direction_source': 'device-trace.jsonl',
                               'effective_interval_source': 'device-trace.jsonl'}
                packet = {'case_id': case, 'authority_kind':
                          'law' if kind == 'governing_law' else 'device',
                          'sources': dict(sources), 'authority_binding': binding,
                          'legal_conclusion': None,
                          'compliance_independently_verified': False}
                if kind == 'governing_law':
                    packet['sources'].pop('device-trace.jsonl')
                check(packet, root, case)
                mutations = []
                for key, value in (('case_id', ASSIGNMENT + '__wrong'),
                                   ('legal_conclusion', 'allowed'),
                                   ('sources', {}),
                                   ('authority_binding', None if state == 'present' else {'fake': True})):
                    changed = dict(packet, **{key: value})
                    try:
                        check(changed, root, case)
                    except ValueError:
                        mutations.append(key)
                    else:
                        raise AssertionError('Authority mutation accepted: ' + key)
                cases.append({'case_id': case, 'negative_mutations_rejected': mutations})
        print(json.dumps({'source_shapes_checked': len(cases), 'cases': cases,
                          'original_authority_observed': False, 'legal_conclusion': None}))


if __name__ == '__main__':
    run()
