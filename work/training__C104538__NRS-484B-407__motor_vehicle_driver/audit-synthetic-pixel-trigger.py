"""Independent raw RGB and provenance audit for C104538 synthetic fallback3."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def main():
    receipt = json.loads((HERE / 'synthetic-pixel-trigger-summary.json').read_text())
    assert receipt['format'] == 'c104538-synthetic-pixel-trigger-proof-v1'
    assert receipt['source_kind'] == 'synthetic_cpu_fixture'
    assert receipt['original_pixel_observed'] is False and receipt['selected'] is False
    root = REPO / receipt['source_dir']
    for label, left_count in [('baseline', 480), ('occluded', 450)]:
        manifest = json.loads((root / label / 'pixel-manifest.json').read_text())
        assert manifest['source_kind'] == 'synthetic_cpu_fixture'
        assert (manifest['width'], manifest['height'], manifest['frames'], manifest['rate_hz']) == (32, 32, 480, 20)
        for role, count in [('reference_left', left_count), ('reference_right', 480)]:
            data = (root / label / (role + '.rgb')).read_bytes()
            rows = [json.loads(line) for line in (root / label / (role + '.jsonl')).read_text().splitlines()]
            assert len(data) == 480 * 32 * 32 * 3 and len(rows) == 480
            visible = 0
            for index, row in enumerate(rows):
                rgb = data[index * 3072:(index + 1) * 3072]
                assert row == {'camera': role, 'frame': index,
                               'rgb_sha256': hashlib.sha256(rgb).hexdigest()}
                pixels = [rgb[j:j + 3] for j in range(0, len(rgb), 3)]
                visible += (pixels.count(b'\xff\x00\x00') >= 12 and
                            pixels.count(b'\xff\xff\xff') >= 16)
            assert visible == count
            value = receipt['cases'][label]['camera_visibility'][role]
            assert value == {'visible_frames': count, 'fraction': count / 480}
        assert receipt['cases'][label]['fallback3_trigger_measured'] == (label == 'occluded')
        assert receipt['cases'][label]['original_pixel_observed'] is False
    assert receipt['negative_error'] == 'Camera source RGB hash differs'
    assert receipt['provenance_negative_error'] == 'Synthetic marker detector cannot audit original pixels'
    damaged = [json.loads(line) for line in (root / 'corrupt_hash/reference_left.jsonl').read_text().splitlines()]
    assert damaged[100]['rgb_sha256'] == '0' * 64
    false_original = json.loads((root / 'false_original_claim/pixel-manifest.json').read_text())
    assert false_original['source_kind'] == 'original_native_capture'
    print(json.dumps({'synthetic_frame_pairs_audited': 960, 'positive_crossing_frames': 30,
                      'source_hash_negative': True, 'original_pixel_observed': False}))


if __name__ == '__main__':
    main()
