"""Construct synthetic RGB positives/negatives for fallback3 threshold logic."""
import hashlib
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE / 'native'))
from pixel_visibility import measure

WIDTH = HEIGHT = 32
FRAMES = 480
ROLES = ('reference_left', 'reference_right')


def frame(show_body):
    data = bytearray(WIDTH * HEIGHT * 3)
    for y in range(6, 26):
        for x in (14, 15):
            offset = (y * WIDTH + x) * 3
            data[offset:offset + 3] = b'\xff\xff\xff'
    if show_body:
        for y in range(12, 16):
            for x in range(20, 24):
                offset = (y * WIDTH + x) * 3
                data[offset:offset + 3] = b'\xff\x00\x00'
    return bytes(data)


def put(path, data):
    path.write_text(json.dumps(data, sort_keys=True, indent=2) + '\n')


def build(source, missing_left):
    source.mkdir(parents=True)
    put(source / 'pixel-manifest.json', {'format': 'c104538-pixel-source-v1',
        'source_kind': 'synthetic_cpu_fixture', 'case_id':
        'training__C104538__NRS-484B-407__motor_vehicle_driver__below_500_ft',
        'width': WIDTH, 'height': HEIGHT, 'frames': FRAMES,
        'rate_hz': 20, 'pixel_semantics': 'red synthetic body; white synthetic centerline'})
    for role in ROLES:
        raw = bytearray()
        rows = []
        for index in range(FRAMES):
            visible = not (role == 'reference_left' and index < missing_left)
            rgb = frame(visible)
            raw.extend(rgb)
            rows.append({'frame': index, 'camera': role,
                         'rgb_sha256': hashlib.sha256(rgb).hexdigest()})
        (source / (role + '.rgb')).write_bytes(raw)
        (source / (role + '.jsonl')).write_text(''.join(json.dumps(row, sort_keys=True) + '\n'
            for row in rows))


def main():
    output = REPO / '.runtime-work/c104538/pixel-trigger-v1'
    if output.exists():
        shutil.rmtree(output)
    baseline = output / 'baseline'
    occluded = output / 'occluded'
    corrupt = output / 'corrupt_hash'
    build(baseline, 0)
    build(occluded, 30)
    shutil.copytree(occluded, corrupt)
    rows = [json.loads(line) for line in (corrupt / 'reference_left.jsonl').read_text().splitlines()]
    rows[100]['rgb_sha256'] = '0' * 64
    (corrupt / 'reference_left.jsonl').write_text(''.join(json.dumps(row, sort_keys=True) + '\n'
        for row in rows))
    values = {label: measure(path) for label, path in [('baseline', baseline), ('occluded', occluded)]}
    assert values['baseline']['camera_visibility']['reference_left']['visible_frames'] == 480
    assert values['occluded']['camera_visibility']['reference_left']['visible_frames'] == 450
    assert values['occluded']['camera_visibility']['reference_right']['visible_frames'] == 480
    assert not values['baseline']['fallback3_trigger_measured']
    assert values['occluded']['fallback3_trigger_measured']
    try:
        measure(corrupt)
    except ValueError as exc:
        assert 'Camera source RGB hash differs' in str(exc)
        negative = str(exc)
    else:
        raise AssertionError('Changed RGB source hash was accepted')
    original_claim = output / 'false_original_claim'
    shutil.copytree(occluded, original_claim)
    manifest = json.loads((original_claim / 'pixel-manifest.json').read_text())
    manifest['source_kind'] = 'original_native_capture'
    put(original_claim / 'pixel-manifest.json', manifest)
    try:
        measure(original_claim)
    except ValueError as exc:
        assert 'Synthetic marker detector cannot audit original pixels' in str(exc)
        provenance_negative = str(exc)
    else:
        raise AssertionError('Synthetic marker source claimed original pixels')
    receipt = {'format': 'c104538-synthetic-pixel-trigger-proof-v1',
        'source_dir': str(output.relative_to(REPO)), 'source_kind': 'synthetic_cpu_fixture',
        'cases': values, 'negative_error': negative,
        'provenance_negative_error': provenance_negative, 'original_pixel_observed': False,
        'selected': False}
    put(HERE / 'synthetic-pixel-trigger-summary.json', receipt)
    print(json.dumps({'baseline_left': 480, 'occluded_left': 450,
        'occluded_right': 480, 'fallback3_trigger': True, 'negative_error': negative,
        'provenance_negative_error': provenance_negative}))


if __name__ == '__main__':
    main()
