"""Independent source-row comparison for three requested passing distances."""
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

HERE = Path(__file__).resolve().parent
DISTANCES = (70, 120, 170)
VARIABLES = {'driver_eye_clear_m', 'oncoming_x_m'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    if not path.is_file():
        raise ValueError('Missing comparison source: ' + path.name)
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def compare(sources):
    original = {}
    for distance in DISTANCES:
        folder = sources / str(distance)
        samples = rows(folder / 'native-observed.jsonl')
        frame_map = rows(folder / 'video_frames.jsonl')
        road = json.loads((folder / 'road-readback.json').read_text())
        if len(samples) != 600 or len(frame_map) != 600:
            raise ValueError('Comparison lacks full 600-frame recording')
        original[distance] = (samples, frame_map, road)
    reference = original[70]
    for distance in DISTANCES:
        samples, frame_map, road = original[distance]
        if frame_map != reference[1] or road != reference[2]:
            raise ValueError('Frame clock or fixed road geometry changed')
        for index, (a, b) in enumerate(zip(reference[0], samples)):
            changed = {key for key in a if a[key] != b[key]}
            if changed - VARIABLES:
                raise ValueError('Undeclared fixed source condition changed at frame ' + str(index))
            if b['driver_eye_clear_m'] != distance:
                raise ValueError('Driver-eye source proxy differs from selected distance')
            if abs(b['oncoming_x_m'] - a['oncoming_x_m'] - (distance - 70)) > 1e-6:
                raise ValueError('Oncoming-track separation differs from requested sweep')
    return {'format': 'c102951-independent-source-comparison-v1',
            'scope': 'synthetic CPU source control; no safety or legal threshold',
            'distances_m': list(DISTANCES),
            'fixed_road_readback_sha256': sha(sources / '70/road-readback.json'),
            'fixed_video_frame_map_sha256': sha(sources / '70/video_frames.jsonl'),
            'variable_source_fields': sorted(VARIABLES),
            'source_hashes': {str(distance): sha(sources / str(distance) / 'native-observed.jsonl')
                              for distance in DISTANCES},
            'frames_per_case': 600,
            'physical_acceptance_claimed': False,
            'legal_acceptance_claimed': False}


def main():
    source = HERE / 'selected-sources'
    proof = compare(source)
    # Directly exercise the two rejection branches without modifying sources.
    missing = HERE / 'nonexistent-selected-sources'
    try:
        compare(missing)
    except ValueError as error:
        if 'Missing comparison source' not in str(error):
            raise
    else:
        raise ValueError('Missing source negative did not reject')
    proof['missing_source_negative_passed'] = True
    with tempfile.TemporaryDirectory(dir=HERE.parents[1] / '.runtime-work',
                                     prefix='c102951-comparison-') as directory:
        altered = Path(directory)
        for distance in DISTANCES:
            shutil.copytree(source / str(distance), altered / str(distance))
        path = altered / '120/native-observed.jsonl'
        lines = path.read_text().splitlines()
        row = json.loads(lines[100])
        row['ego_x_m'] += 1
        lines[100] = json.dumps(row, sort_keys=True)
        path.write_text('\n'.join(lines) + '\n')
        try:
            compare(altered)
        except ValueError as error:
            if 'Undeclared fixed source condition changed' not in str(error):
                raise
        else:
            raise ValueError('Changed fixed condition negative did not reject')
    proof['changed_fixed_condition_negative_passed'] = True
    target = HERE / 'selected-comparison-audit.json'
    target.write_text(json.dumps(proof, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'passed': True, 'sha256': sha(target)}))


if __name__ == '__main__':
    main()
