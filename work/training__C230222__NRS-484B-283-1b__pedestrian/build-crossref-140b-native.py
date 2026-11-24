"""Survey-gated white-cane prop context on the frozen C230222 curb cell."""
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BASE = HERE.name
LABELS = ('cane_prop_candidate', 'no_cane_prop')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def replace_one(text, before, after):
    if text.count(before) != 1:
        raise ValueError('Unexpected Native source shape: ' + before)
    return text.replace(before, after)


def main():
    template = json.loads((HERE / 'v2-primary/probe_1/construction.json').read_text())
    cases = []
    for label in LABELS:
        case = BASE + '__crossref_lvmc_11_30_140_b_' + label
        construction = copy.deepcopy(template)
        construction['case_id'] = case
        construction['status'] = 'unselected_white_cane_prop_survey_cpu_construction'
        for item in construction['files']:
            path, content = item['path'], item['content']
            if path == 'engineering.py':
                content = replace_one(content,
                    "if suffix not in ('probe_1', 'probe_2') or ident not in IDS:",
                    "if suffix not in ('crossref_lvmc_11_30_140_b_cane_prop_candidate', 'crossref_lvmc_11_30_140_b_no_cane_prop') or ident != 'primary':")
                content = replace_one(content,
                    "start = .5 if suffix == 'probe_1' else 3.5", "start = .5")
            elif path == 'runner.py':
                content = replace_one(content,
                    "if plan['engineering']['pedestrian_departure_s'] not in (.5, 3.5):",
                    "if plan['engineering']['pedestrian_departure_s'] != .5:")
                content = replace_one(content,
                    "owned.extend((walker, vehicle))",
                    """owned.extend((walker, vehicle))
        cane_prop_id = None
        if config['case_suffix'].endswith('cane_prop_candidate'):
            options = sorted((bp for bp in library.filter('static.prop.*')
                              if 'cane' in bp.id.lower() or 'walking_stick' in bp.id.lower()),
                             key=lambda bp: bp.id)
            if not options:
                raise RuntimeError('No Native cane or walking-stick prop blueprint; capability requires tested receipt')
            marker = world.try_spawn_actor(options[0], carla.Transform(
                carla.Location(x=.25, y=.12, z=.7)), attach_to=walker)
            if marker is None:
                raise RuntimeError('Native cane prop attachment failed')
            cane_prop_id = marker.id
            owned.append(marker)""")
                content = replace_one(content,
                    "'driver_capability_measured': False, 'introductory_exceptions_reviewed': False,",
                    "'driver_capability_measured': False, 'introductory_exceptions_reviewed': False,\n            'requested_cane_prop_id': cane_prop_id, 'cane_pixels_verified': False,\n            'pedestrian_blindness_verified': False, 'driver_precautions_reviewed': False,")
            elif path == 'finalize.py':
                content = replace_one(content,
                    "expected = 'conditional_yield_possible' if config['case_suffix'] == 'probe_1' else 'conditional_yield_impossible'",
                    "expected = 'conditional_yield_possible'")
            elif path == 'tests/test_offline.py':
                content = replace_one(content,
                    ".5 if config['case_suffix'] == 'probe_1' else 3.5)", ".5)")
                start = content.index('    def test_fallback_trigger_boundaries(self):')
                end = content.find('\n    def ', start + 1)
                content = content[:start] + (content[end:] if end >= 0 else '')
            elif path == 'config.json':
                config = json.loads(content)
                config['case_id'] = case
                config['selected_case_id'] = case
                config['case_suffix'] = case.split('__')[-1]
                config['case']['case_id'] = case
                config['supported_case_ids'] = [BASE + '__crossref_lvmc_11_30_140_b_' + one for one in LABELS]
                content = json.dumps(config, indent=2) + '\n'
            item['content'] = content
        target = HERE / 'crossref-140b-native' / label / 'construction.json'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(construction, indent=2) + '\n')
        cases.append({'case_id': case, 'construction': str(target.relative_to(HERE)),
                      'construction_sha256': digest(target),
                      'cane_prop_requested': label == 'cane_prop_candidate',
                      'native_cane_prop_available_verified': False,
                      'original_cane_pixels_verified': False,
                      'pedestrian_blindness_verified': False,
                      'driver_precautions_reviewed': False,
                      'status': 'unselected_cpu_construction'})
    manifest = {'format': 'worker-execution-manifest', 'assignment_id': BASE,
                'runtime_manifest_sha256': digest(ROOT / 'runtime/SOURCE-MANIFEST.json'),
                'status': 'unselected_survey_gated_cane_context_cpu_construction',
                'cases': cases}
    (HERE / 'crossref-140b-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'cases': len(cases), 'physical_marker_verified': False}))


if __name__ == '__main__':
    main()
