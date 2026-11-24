"""Author survey-gated overhead-crossing context alternatives on C230222."""
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BASE = HERE.name
LABELS = ('overhead_candidate', 'no_overhead')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def replace_one(text, before, after):
    if text.count(before) != 1:
        raise ValueError('Unexpected Native source shape: ' + before)
    return text.replace(before, after)


def main():
    template = json.loads((HERE / 'v2-primary/probe_1/construction.json').read_text())
    plain = (HERE / 'native/road.xodr').read_text()
    object_xml = ('    <objects>\n'
                  '      <object id="201" name="PedestrianOverheadCandidate" type="bridge" '
                  's="20" t="0" zOffset="5" hdg="-1.5707963267948966" length="7" width="3" />\n'
                  '    </objects>')
    authored = replace_one(plain, '<objects />', object_xml)
    # The object is an authored survey target. Native rendering, usable pedestrian
    # access and original pixels remain unverified until an actual capture.
    roadpath = HERE / 'native/road-overhead-candidate.xodr'
    roadpath.write_text(authored)
    cases = []
    for label in LABELS:
        case = BASE + '__crossref_lvmc_11_30_060_b_' + label
        construction = copy.deepcopy(template)
        construction['case_id'] = case
        construction['status'] = 'unselected_survey_gated_overhead_context_cpu_construction'
        for item in construction['files']:
            path, content = item['path'], item['content']
            if path == 'road.xodr':
                content = authored if label == 'overhead_candidate' else plain
            elif path == 'geometry.py' and label == 'overhead_candidate':
                content = replace_one(content,
                    "or road.findall('objects/object'):",
                    "or len(road.findall('objects/object')) != 1 or road.find('objects/object').get('type') != 'bridge':")
            elif path == 'engineering.py':
                content = replace_one(content,
                    "if suffix not in ('probe_1', 'probe_2') or ident not in IDS:",
                    "if suffix not in ('crossref_lvmc_11_30_060_b_overhead_candidate', 'crossref_lvmc_11_30_060_b_no_overhead') or ident != 'primary':")
                content = replace_one(content,
                    "start = .5 if suffix == 'probe_1' else 3.5", "start = .5")
            elif path == 'runner.py':
                content = replace_one(content,
                    "if plan['engineering']['pedestrian_departure_s'] not in (.5, 3.5):",
                    "if plan['engineering']['pedestrian_departure_s'] != .5:")
                content = replace_one(content,
                    "'case_id': config['case_id'], 'candidate_id': config['candidate_id'],",
                    "'case_id': config['case_id'], 'candidate_id': config['candidate_id'],\n            'overhead_candidate_native_visibility_unverified': True,")
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
                config['supported_case_ids'] = [BASE + '__crossref_lvmc_11_30_060_b_' + one for one in LABELS]
                content = json.dumps(config, indent=2) + '\n'
            item['content'] = content
        target = HERE / 'crossref-060b-native' / label / 'construction.json'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(construction, indent=2) + '\n')
        cases.append({'case_id': case, 'construction': str(target.relative_to(HERE)),
                      'construction_sha256': digest(target),
                      'authored_overhead_candidate': label == 'overhead_candidate',
                      'status': 'unselected_cpu_construction',
                      'native_overhead_visibility_verified': False,
                      'pedestrian_tunnel_or_overhead_provided_verified': False})
    manifest = {'format': 'worker-execution-manifest', 'assignment_id': BASE,
                'runtime_manifest_sha256': digest(ROOT / 'runtime/SOURCE-MANIFEST.json'),
                'status': 'unselected_survey_gated_overhead_context_cpu_construction',
                'cases': cases}
    (HERE / 'crossref-060b-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'cases': len(cases), 'authored_candidate_road_sha256': digest(roadpath)}))


if __name__ == '__main__':
    main()
