"""Atomic result.json completion records; usable from the CARLA interpreter."""
import hashlib
import json
import os
from pathlib import Path
import tempfile


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for part in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(part)
    return h.hexdigest()


def atomic_result(path, value):
    path = Path(path)
    fd, name = tempfile.mkstemp(prefix='.' + path.name, dir=str(path.parent))
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(value, stream, indent=2, allow_nan=False)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, str(path))
    finally:
        if os.path.exists(name):
            os.unlink(name)


def normalize_recording_references(result, directory):
    """Project exact file references; preserve every original value and receipt."""
    result = json.loads(json.dumps(result))
    changes = []
    videos = result.get('video_references', [])
    if not isinstance(videos, list):
        raise ValueError('Video references must be a list')
    if any(isinstance(item, dict) for item in videos):
        paths = []
        for item in videos:
            path = item.get('path') if isinstance(item, dict) else item
            if not isinstance(path, str) or not path:
                raise ValueError('Video reference needs an explicit file path')
            paths.append(path)
        previous = result.get('runner_video_reference_metadata')
        if previous is not None and previous != videos:
            raise ValueError('Conflicting original video reference metadata')
        result['runner_video_reference_metadata'] = videos
        result['video_references'] = paths
        changes.append({'field': 'video_references', 'original': videos, 'projected': paths})
    for item in result.get('recording_evidence', []):
        ref = item.get('reference')
        if not isinstance(ref, str) or '#' not in ref:
            continue
        filename, pointer = ref.split('#', 1)
        name = item.get('name')
        if not isinstance(name, str) or pointer != '/' + name.replace('~', '~0').replace('/', '~1'):
            raise ValueError('Context reference must select its exact declared context name')
        path = Path(filename)
        path = path if path.is_absolute() else Path(directory) / path
        path = path.resolve()
        if Path(directory).resolve() not in path.parents or not path.is_file():
            raise ValueError('Context reference escapes attempt or is missing')
        context = json.loads(path.read_text())
        if not isinstance(context, dict) or name not in context:
            raise ValueError('Context reference selects a missing context field')
        item['reference'] = filename
        changes.append({'field': 'recording_evidence', 'name': name, 'original': ref, 'projected': filename})
    if changes:
        result['reference_normalization'] = {'kind': 'exact_file_reference_projection', 'changes': changes,
            'policy': 'Values, unknowns, targets, timing and original metadata are preserved; acceptance requires all normal checks.'}
    return result


def seal(directory, binding):
    directory = Path(directory)
    original = json.loads((directory / 'result.json').read_text())
    result = normalize_recording_references(original, directory)
    if result != original:
        preserved = directory / 'runner_result_before_reference_normalization.json'
        if not preserved.exists():
            atomic_result(preserved, original)
    # Logs may still be written by process teardown; only finalized evidence is sealed.
    hashes = {str(p.relative_to(directory)): sha(p) for p in sorted(directory.rglob('*'))
              if p.is_file() and p.name != 'result.json' and not p.name.endswith('.log')
              and not p.name.startswith('.') and p.name not in ('failure.json',)}
    for ref in [result.get('trace_reference'), result.get('video_frame_map_reference')] + result.get('video_references', []):
        if not ref:
            raise ValueError('Cannot seal incomplete recording references')
        path = Path(ref)
        path = path if path.is_absolute() else directory / path
        relative = str(path.resolve().relative_to(directory.resolve()))
        if relative not in hashes:
            raise ValueError('Cannot seal missing evidence: ' + str(ref))
    body={k:v for k,v in result.items() if k!='completion'}
    result_hash=hashlib.sha256(json.dumps(body,sort_keys=True,allow_nan=False).encode()).hexdigest()
    result['completion'] = {'binding': binding, 'artifact_hashes': hashes, 'result_hash': result_hash}
    atomic_result(directory / 'result.json', result)
    return result


def verify(directory, binding):
    directory = Path(directory)
    result = json.loads((directory / 'result.json').read_text())
    completion = result.get('completion', {})
    if completion.get('binding') != binding or not completion.get('artifact_hashes'):
        raise ValueError('Missing or mismatched atomic completion binding')
    body={k:v for k,v in result.items() if k!='completion'}
    if hashlib.sha256(json.dumps(body,sort_keys=True,allow_nan=False).encode()).hexdigest()!=completion.get('result_hash'):
        raise ValueError('Completion result changed after publication')
    for name, expected in completion['artifact_hashes'].items():
        path = (directory / name).resolve()
        if directory.resolve() not in path.parents or not path.is_file() or sha(path) != expected:
            raise ValueError('Completion artifact missing or changed: ' + name)
    return result
