"""Build exact C111125 diagnostic bundles from the source-bound case plan."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = HERE.name
SOURCES = ('signal_exception.py', 'original_capture.py', 'saved_measurement.py',
           'comparison_audit.py', 'delivery_audit.py', 'media_decode.py')

RUNNER = '''"""C111125 exact diagnostic preflight; unsourced Native launch is refused."""
import argparse
import hashlib
import json
from pathlib import Path


def check():
    root = Path(__file__).resolve().parent
    config = json.loads((root / "config.json").read_text(encoding="utf-8"))
    source = (root / "case-plan.json").read_bytes()
    if hashlib.sha256(source).hexdigest() != config["plan_sha256"]:
        raise ValueError("C111125 exact case plan changed")
    case_id = config["selected_case_id"]
    if not case_id.startswith(config["assignment_id"] + "__"):
        raise ValueError("C111125 foreign exact case")
    matches = [row for row in json.loads(source)["cases"] if row["case_id"] == case_id]
    if len(matches) != 1 or matches[0]["scenario_parameters"] != config["case_parameters"]:
        raise ValueError("C111125 exact case construction changed")
    if config["fps"] != 20 or config["frame_count"] != 900 or config["duration_s"] != 45:
        raise ValueError("C111125 original timebase changed")
    if config["cameras"] != ["overview", "approach", "reference_corner", "driver_reference"]:
        raise ValueError("C111125 pinned camera profile changed")
    if config["required_sources"] != ["loaded_map", "official_composite_head", "stopping_reference", "causal_detector_or_malfunction", "participant_tracks", "original_camera_media"]:
        raise ValueError("C111125 required originals changed")
    return case_id


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    args = parser.parse_args()
    case_id = check()
    if args.check:
        print("diagnostic C111125 case passed: " + case_id)
        return
    raise ValueError("Reviewed original C111125 map, composite head, detector and camera sources required")


if __name__ == "__main__":
    main()
'''

TEST = '''import json
from pathlib import Path
import unittest
from unittest.mock import patch
import runner


class BundleTests(unittest.TestCase):
    def test_exact_case_binding(self):
        root = Path(__file__).resolve().parents[1]
        self.assertEqual(runner.check(), json.loads((root / "config.json").read_text())["selected_case_id"])

    def test_unsourced_capture_rejected(self):
        with patch("sys.argv", ["runner.py", "--output-dir", "."]):
            with self.assertRaisesRegex(ValueError, "Reviewed original C111125"):
                runner.main()


if __name__ == "__main__":
    unittest.main()
'''


def build():
    source = (HERE / 'case-plan.json').read_bytes()
    plan = json.loads(source)
    cases = plan['cases']
    if len(cases) != 6 or len({row['case_id'] for row in cases}) != 6:
        raise ValueError('Six distinct C111125 exact cases required')
    output_rows = []
    for row in cases:
        case_id = row['case_id']
        if not case_id.startswith(AID + '__'):
            raise ValueError('Foreign C111125 exact case')
        suffix = case_id.removeprefix(AID + '__')
        config = {'assignment_id': AID, 'law_id': 'NRS-484B-307-9b',
                  'cell_id': 'C111125', 'actor': 'motorcycle_or_moped_operator',
                  'selected_case_id': case_id,
                  'case_parameters': row['scenario_parameters'],
                  'plan_sha256': hashlib.sha256(source).hexdigest(),
                  'fps': 20, 'frame_count': 900, 'duration_s': 45,
                  'cameras': ['overview', 'approach', 'reference_corner',
                              'driver_reference'], 'required_atoms': [],
                  'required_sources': ['loaded_map', 'official_composite_head',
                                       'stopping_reference', 'causal_detector_or_malfunction',
                                       'participant_tracks', 'original_camera_media'],
                  'diagnostic_only': True}
        files = {name: (HERE / name).read_text(encoding='utf-8') for name in SOURCES}
        files.update({'runner.py': RUNNER, 'case-plan.json': source.decode('utf-8'),
                      'config.json': json.dumps(config, indent=2) + '\n',
                      'tests/test_bundle.py': TEST})
        construction = {'law_id': config['law_id'], 'cell_id': config['cell_id'],
                        'actor': config['actor'], 'case_id': case_id,
                        'entrypoint': 'runner.py', 'diagnostic_only': True,
                        'recording_description': {'status': 'original_sources_pending',
                                                  'channels': config['cameras']},
                        'files': [{'path': name, 'content': content}
                                  for name, content in files.items()]}
        path = HERE / ('construction-' + suffix + '.json')
        path.write_text(json.dumps(construction, indent=2) + '\n', encoding='utf-8')
        output_rows.append({'case_id': case_id, 'construction': path.name,
                            'construction_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                            'candidate_risk': row['physical_risk_assessment']})
    (HERE / 'execution-manifest.draft.json').write_text(json.dumps({
        'assignment_id': AID, 'status': 'diagnostic_original_sources_pending',
        'cases': output_rows}, indent=2) + '\n', encoding='utf-8')
    print('built', len(output_rows), 'exact C111125 diagnostic constructions')


if __name__ == '__main__':
    build()
