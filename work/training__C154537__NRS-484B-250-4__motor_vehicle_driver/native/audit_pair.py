"""Independent source-level contrast audit; this is not a legal finding."""
import argparse
import hashlib
import json
from pathlib import Path

from measure_saved import measure


FIXED_FIELDS = ('source_kind', 'road_sha256', 'stop_line_present',
                'near_side_crosswalk_present', 'sidewalk_derived_crosswalk_reviewed',
                'signal_installed', 'signal_uncovered',
                'official_device_provenance_reviewed',
                'through_highway_provenance_reviewed', 'signal_id',
                'intersection_entry_front_x_m')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit(stopped, rolling):
    stopped, rolling = Path(stopped), Path(rolling)
    positive, negative = measure(stopped), measure(rolling)
    if not positive['complete_cessation_sample_before_entry']:
        raise ValueError('Controlled stop case lacks original cessation')
    if negative['complete_cessation_sample_before_entry']:
        raise ValueError('Rolling contrast contains a complete stop')
    a = json.loads((stopped / 'scene-survey.json').read_text())
    b = json.loads((rolling / 'scene-survey.json').read_text())
    differences = [key for key in FIXED_FIELDS if a.get(key) != b.get(key)]
    if differences:
        raise ValueError('Fixed construction/source context differs: ' + ', '.join(differences))
    return {'format': 'c154537-source-pair-audit-v1', 'passed': True,
            'comparison': 'complete cessation before entry versus rolling entry',
            'legal_verdict_claimed': False, 'physical_acceptance_claimed': False,
            'source_sha256': {
                label: {name: sha(directory / name) for name in
                        ('scene-survey.json', 'native-motion.jsonl', 'video_frames.jsonl')}
                for label, directory in (('stopped', stopped), ('rolling', rolling))},
            'fixed_fields': list(FIXED_FIELDS),
            'stopped_entry_frame': positive['entry_frame'],
            'rolling_entry_frame': negative['entry_frame']}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--stopped', type=Path, required=True)
    parser.add_argument('--rolling', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('Use a fresh audit output path')
    result = audit(args.stopped, args.rolling)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'passed': True, 'legal_verdict_claimed': False}))


if __name__ == '__main__':
    main()
