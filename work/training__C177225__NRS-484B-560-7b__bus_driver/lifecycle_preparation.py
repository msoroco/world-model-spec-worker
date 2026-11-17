"""Independently verify original capture closure before saved processing.

This reads real receipt files at later local execution. Unit fixtures test the
contract only and do not attest that an operator released a CARLA server.
"""
import hashlib
import json
from pathlib import Path

EVENTS = ['capture_finished', 'encoders_closed', 'restoration_verified',
          'native_exit', 'owner_released', 'saved_processing_started']


def _read(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError('Missing lifecycle source: ' + path.name)
    return json.loads(path.read_text())


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inspect(attempt, owner_receipt, processing_receipt):
    attempt = Path(attempt)
    seal_path = attempt / 'capture-seal.json'
    exit_path = attempt / 'native-exit.json'
    seal = _read(seal_path)
    exit_record = _read(exit_path)
    owner = _read(owner_receipt)
    processing = _read(processing_receipt)
    config = _read(attempt / 'config.json')
    if (seal.get('format') != 'worker-sealed-capture' or
            seal.get('provenance_kind') != 'native' or
            seal.get('diagnostic_fixture') is not False or
            seal.get('events') != EVENTS[:3] or
            seal.get('restoration', {}).get('restored') is not True):
        raise ValueError('Original capture was not sealed after restoration')
    sources = seal.get('sources', {})
    if not sources or any(not (attempt / name).is_file() or _sha(attempt / name) != digest
                          for name, digest in sources.items()):
        raise ValueError('Sealed original source changed or is missing')
    revision = seal.get('native_revision', {})
    if (revision.get('construction_sha256') != _sha(attempt / 'construction.json') or
            revision.get('runner_sha256') != _sha(attempt / 'runner.py')):
        raise ValueError('Native implementation revision differs')
    if (exit_record.get('event') != 'native_exit' or
            exit_record.get('capture_seal_sha256') != _sha(seal_path) or
            exit_record.get('native_revision') != revision):
        raise ValueError('Native exit receipt differs')
    if (owner.get('event') != 'owner_released' or
            owner.get('operator_attested') is not True or
            owner.get('native_construction_sha256') != revision['construction_sha256'] or
            owner.get('native_exit_sha256') != _sha(exit_path)):
        raise ValueError('Operator owner release is absent or stale')
    if (processing.get('format') != 'worker-saved-processing' or
            processing.get('recorded_only') is not True or
            processing.get('passed') is not True or
            processing.get('originals_preserved') is not True or
            processing.get('case_id') != config.get('case_id') or
            processing.get('events', [None])[0] != 'saved_processing_started'):
        raise ValueError('Saved-only processing receipt differs')
    for name, digest in sources.items():
        if processing.get('original_source_hashes', {}).get(name) != digest:
            raise ValueError('Saved processing did not preserve sealed source: ' + name)
    return {'events': EVENTS, 'exit_code': 0,
            'case_id': config['case_id'], 'source_count': len(sources),
            'scope': 'receipt ordering and source binding; no physical or legal acceptance'}
