"""Record the selected exact source and four-camera coverage contract."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    path = HERE / 'case-plan.json'
    plan = json.loads(path.read_text())
    for term, mapping in plan['source_observation_mapping'].items():
        mapping['channels'] = [term]
        mapping['evidence'] = ('Source-bound selected Native channel; all 600 frames retained, '
                               'original sight and legal hazard interpretation await review.')
    plan['camera_plan'] = {
        'profile': 'overview1080-capability',
        'duration_s': 30,
        'composition': 'synchronized_four_view_primary',
        'coverage': [
            {'view': 'overview', 'subject': 'ego, other vehicle, crest or curve and roadside wall',
             'interval': 'all 600 original frames'},
            {'view': 'approach', 'subject': 'ego path and possible opposing approach',
             'interval': 'all 600 original frames'},
            {'view': 'reference_corner', 'subject': 'road boundary and body relative to centre line',
             'interval': 'all 600 original frames'},
            {'view': 'driver_reference', 'subject': 'original driver-height sightline and wall occlusion',
             'interval': 'all 600 original frames'}],
        'limitations': ['Authored placement is a plan; original pixels, roadway authority '
                        'and hazard-creating obstruction require independent local review.']}
    plan['runtime_uncertainties'] = [
        'Selected CPU fixtures do not establish original Native body motion, sightline or pixels.',
        'Actual generated roadside wall occlusion remains subject to original cast-ray and camera review.',
        'One-way public highway authority and hazard-creating distance remain unquantified legal judgments.']
    path.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({'camera_views': len(plan['camera_plan']['coverage']),
                      'mapped_terms': len(plan['source_observation_mapping'])}))


if __name__ == '__main__':
    main()
