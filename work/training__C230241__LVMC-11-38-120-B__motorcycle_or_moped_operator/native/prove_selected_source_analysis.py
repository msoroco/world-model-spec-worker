"""Exercise the exact 600-frame saved lighting analysis and missing-source rejection."""
import argparse
import json
import shutil
import tempfile
from pathlib import Path

from selected_source_analysis import SOURCES, selected_lighting_measurement, sha


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', required=True)
    args = parser.parse_args()
    source = Path(args.source).resolve()
    if not all((source / name).is_file() for name in SOURCES):
        raise ValueError('Regenerate the 600-frame source diagnostic first')
    root = Path(__file__).resolve().parents[3] / '.runtime-work'
    root.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='c230241-selected-analysis-', dir=root) as temporary:
        scratch = Path(temporary)
        positive = selected_lighting_measurement(source, scratch / 'positive-derived')
        assert positive['frames'] == 600 and positive['diagnostic_only'] is True
        assert positive['counts']['required_burning_frames'] == 399
        assert positive['counts']['headlamp_dark_frames'] == 1
        assert positive['counts']['tail_lamp_dark_frames'] == 0
        assert positive['physical_visibility_verified'] is False
        negative = scratch / 'negative-source'
        negative.mkdir()
        for name in SOURCES:
            if name != 'lighting-measure-context.json':
                shutil.copyfile(source / name, negative / name)
        try:
            selected_lighting_measurement(negative, scratch / 'negative-derived')
        except ValueError as error:
            assert str(error) == 'Missing required source: lighting-measure-context.json'
        else:
            raise AssertionError('Missing measurement context was accepted')
    receipt = {
        'format': 'c230241-selected-source-analysis-proof-v1',
        'passed': True,
        'diagnostic_only': True,
        'source_hashes': positive['source_hashes'],
        'analysis_script_sha256': sha(Path(__file__).with_name('selected_source_analysis.py')),
        'checks': ['600-frame binding', 'source-joined measurement',
                   'missing measurement context rejected'],
        'physical_visibility_verified': False,
        'legal_verdict_claimed': False,
    }
    destination = Path(__file__).with_name('selected-source-analysis-proof.json')
    destination.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'passed': True, 'checks': len(receipt['checks'])}))


if __name__ == '__main__':
    main()
