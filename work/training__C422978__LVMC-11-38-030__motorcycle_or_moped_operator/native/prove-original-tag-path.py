"""Exercise the runner's original_native tag with synthetic saved rows only."""
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

from measure_saved import measure as measure_occupancy
from measure_context import measure as measure_context

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    source = HERE / 'saved-fixtures/witness_2/primary'
    context = HERE / 'context-fixtures/witness_2/primary/city-context.json'
    with tempfile.TemporaryDirectory(prefix='c422978-original-tag-') as temporary:
        attempt = Path(temporary)
        for name in ('native-map-readback.json', 'video_frames.jsonl', 'capture/evidence.jsonl'):
            target = attempt / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source / name, target)
        rows = [json.loads(line) for line in (source / 'native-observed.jsonl').read_text().splitlines()]
        assert len(rows) == 480 and {row['source_kind'] for row in rows} == {'synthetic_cpu'}
        for row in rows:
            row['source_kind'] = 'original_native'
        observed = attempt / 'native-observed.jsonl'
        observed.write_text(''.join(json.dumps(row, allow_nan=False) + '\n' for row in rows))
        occupancy = measure_occupancy(attempt)
        spatial = measure_context(attempt, context)
        assert occupancy['source_kind'] == spatial['source_kind'] == 'original_native'
        assert occupancy['frames'] == spatial['frames'] == 480
        assert occupancy['moving_sidewalk_overlap_frames'] == 400
        assert spatial['moving_sidewalk_intersection_frames'] == 400
        assert spatial['city_authority_reviewed'] is False
        assert spatial['driveway_rule_composition_reviewed'] is False
        assert spatial['legal_verdict'] is None
        original_hash = sha(observed)
        rows[17]['source_kind'] = 'native_original'
        observed.write_text(''.join(json.dumps(row, allow_nan=False) + '\n' for row in rows))
        negative_hash = sha(observed)
        rejected = {}
        for label, processor in (('occupancy', measure_occupancy),
                                 ('spatial', lambda path: measure_context(path, context))):
            try:
                processor(attempt)
            except ValueError as error:
                if 'provenance differs' not in str(error):
                    raise
                rejected[label] = str(error)
            else:
                raise AssertionError('Mixed saved provenance accepted by ' + label)
    proof = {
        'format': 'c422978-original-tag-cpu-path-v1',
        'scope': 'Synthetic rows retagged solely to test the original Native parser branch; no original capture or City authority claimed',
        'source_fixture_sha256': sha(source / 'native-observed.jsonl'),
        'context_sha256': sha(context),
        'occupancy_processor_sha256': sha(HERE / 'measure_saved.py'),
        'spatial_processor_sha256': sha(HERE / 'measure_context.py'),
        'retagged_observed_sha256': original_hash,
        'mixed_provenance_observed_sha256': negative_hash,
        'positive': {'frames': 480,
                     'moving_sidewalk_overlap_frames': occupancy['moving_sidewalk_overlap_frames'],
                     'moving_sidewalk_intersection_frames': spatial['moving_sidewalk_intersection_frames'],
                     'city_authority_reviewed': False,
                     'driveway_rule_composition_reviewed': False,
                     'legal_verdict': None},
        'negative_rejections': rejected,
        'original_native_observed': False,
        'accepted': False}
    output = HERE / 'original-tag-cpu-proof.json'
    output.write_text(json.dumps(proof, indent=2) + '\n')
    print(json.dumps({'positive_frames': 480, 'negative_rejections': len(rejected)}))


if __name__ == '__main__':
    main()
