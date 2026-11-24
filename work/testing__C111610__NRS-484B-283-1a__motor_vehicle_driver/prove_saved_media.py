"""Retain one explicitly synthetic source join and its independent media audit."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT / 'tests'))

from native_capture import capture
from saved_media_audit import audit
from test_native_capture import Adapter, SCENE, packet


def main():
    scratch = REPO / '.runtime-work' / 'c111610-media-proof-v1'
    scratch.mkdir(parents=True, exist_ok=True)
    site = scratch / 'site.json'
    exception = scratch / 'exception.json'
    site.write_text(json.dumps(packet()) + '\n')
    exception.write_text(json.dumps({
        'case_id': json.loads(SCENE.read_text())['case_id'],
        'status': 'none_identified',
        'source_refs': ['diagnostic/exception-source.json']}) + '\n')
    dimensions = {name: (2, 2) for name in
                  ('overview', 'approach', 'reference_corner', 'driver_reference')}
    attempt = scratch / 'attempt'
    if not attempt.exists():
        capture(Adapter(site.read_bytes()), SCENE, site, exception,
                attempt, dimensions=dimensions)
    report = audit(attempt, SCENE, dimensions=dimensions)
    report['provenance_kind'] = 'synthetic_fixture'
    report['diagnostic_fixture'] = True
    report['scratch_attempt'] = str(attempt.relative_to(REPO))
    output = ROOT / 'saved-media-diagnostic.json'
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    print(f'checked {report["decoded_view_frames"]} original diagnostic PNG frames')
    print(f'physical acceptance {report["physical_acceptance"]}; pixel visibility {report["pixel_visibility"]}')


if __name__ == '__main__':
    main()
