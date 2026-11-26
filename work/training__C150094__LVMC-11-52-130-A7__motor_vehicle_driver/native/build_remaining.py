"""Materialize two independent Native driveway comparison constructions."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = 'training__C150094__LVMC-11-52-130-A7__motor_vehicle_driver'
VARIANTS = {'01': {'gap_m': 2.0, 'authority': False},
            '03': {'gap_m': 1.2, 'authority': True},
            '04': {'gap_m': 1.524, 'authority': False},
            '05': {'gap_m': 0.0, 'authority': False},
            '06': {'gap_m': 1.2, 'authority': False},
            '07': {'gap_m': 1.2, 'authority': True},
            '08': {'gap_m': 1.2, 'authority': True},
            '09': {'gap_m': 1.2, 'authority': True},
            '10': {'gap_m': 1.2, 'authority': False}}


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    original = HERE / 'selected_primary'
    entries = [entry for entry in json.loads((HERE / 'selected-offline-manifest.json').read_text())['cases']
               if entry['case_id'].endswith('__probe_02')]
    for probe, variant in VARIANTS.items():
        case = AID + '__probe_' + probe
        bundle = HERE / ('probe_' + probe)
        bundle.mkdir(exist_ok=True)
        runner = (original / 'runner.py').read_text().replace('__probe_02', '__probe_' + probe)
        if probe == '05':
            marker = "        raise ValueError('Surveyed stop point does not target this exact driveway gap')\n"
            addition = ("    overlap = max(0.0, min(high, opening[1]) - max(low, opening[0]))\n"
                        "    if abs(overlap - config['target_front_overlap_m']) > .25:\n"
                        "        raise ValueError('Surveyed stop point does not target front overlap')\n")
            if marker not in runner:
                raise ValueError('Front overlap guard insertion point changed')
            runner = runner.replace(marker, marker + addition)
        if probe == '06':
            marker = "    config = json.loads((HERE / 'config.json').read_text())\n"
            addition = ("    if survey.get('driveway_kind') != 'public' or not survey.get('driveway_kind_source'):\n"
                        "        raise ValueError('Exact public driveway survey source required')\n")
            if marker not in runner:
                raise ValueError('Public driveway survey insertion point changed')
            point = runner.rfind(marker)
            runner = runner[:point] + addition + runner[point:]
        if probe == '10':
            marker = "    config = json.loads((HERE / 'config.json').read_text())\n"
            addition = ("    if (survey.get('usps_vehicle') is not True or survey.get('usps_official_business') is not True or\n"
                        "            not survey.get('usps_vehicle_source') or not survey.get('usps_official_business_source')):\n"
                        "        raise ValueError('Exact USPS official-business source required')\n")
            if marker not in runner:
                raise ValueError('USPS survey insertion point changed')
            point = runner.rfind(marker)
            runner = runner[:point] + addition + runner[point:]
        (bundle / 'runner.py').write_text(runner)
        (bundle / 'finalize.py').write_text((original / 'finalize.py').read_text())
        config = json.loads((original / 'config.json').read_text())
        config['case_id'] = case
        config['selected_case_id'] = case
        config['supported_case_ids'] = [case]
        config['case']['case_id'] = case
        config['target_gap_m'] = variant['gap_m']
        if probe == '05':
            config['target_front_overlap_m'] = 0.5
        if probe == '06':
            config['expected_driveway_kind'] = 'public'
        if probe == '10':
            config['expected_usps_official_business'] = True
        branch = {'01': 'far-no-exception', '03': 'near-private-authority',
                  '04': 'at-five-feet-no-exception',
                  '05': 'front-overlap-no-exception',
                  '06': 'public-driveway-near-no-exception',
                  '07': 'near-private-controller-authority',
                  '08': 'near-private-family-authority',
                  '09': 'near-private-invitee-authority',
                  '10': 'near-usps-official-business'}[probe]
        config['case'] = {'case_id': case,
                          'recording_description': config['recording_description'],
                          'branch': branch}
        write(bundle / 'config.json', config)
        tests = (original / 'tests/test_bundle.py').read_text()
        if probe == '01':
            tests = tests.replace('[14.2, 0, 0]', '[15.0, 0, 0]')
        if probe == '04':
            tests = tests.replace('[14.2, 0, 0]', '[14.524, 0, 0]')
        if probe == '05':
            tests = tests.replace('[14.2, 0, 0]', '[12.5, 0, 0]')
            tests = tests.replace("survey['stop_centre_xyz_m'] = [10, 0, 0]",
                                  "survey['stop_centre_xyz_m'] = [15, 0, 0]")
            tests = tests.replace("        survey['road_axis_xy'] = [2, 0]",
                                  "        survey['stop_centre_xyz_m'] = [11, 0, 0]\n"
                                  "        with self.assertRaisesRegex(ValueError, 'front overlap'):\n"
                                  "            survey_check(survey)\n"
                                  "        survey['stop_centre_xyz_m'] = [12.5, 0, 0]\n"
                                  "        survey['road_axis_xy'] = [2, 0]")
        if probe == '06':
            tests = tests.replace("'road_id': 7}",
                                  "'road_id': 7, 'driveway_kind': 'public', 'driveway_kind_source': 'test'}")
            tests = tests.replace("        survey['road_axis_xy'] = [2, 0]",
                                  "        survey['driveway_kind'] = 'private'\n"
                                  "        with self.assertRaisesRegex(ValueError, 'public driveway'):\n"
                                  "            survey_check(survey)\n"
                                  "        survey['driveway_kind'] = 'public'\n"
                                  "        survey['road_axis_xy'] = [2, 0]")
        if probe == '10':
            tests = tests.replace("'road_id': 7}",
                                  "'road_id': 7, 'usps_vehicle': True, 'usps_official_business': True, 'usps_vehicle_source': 'test', 'usps_official_business_source': 'test'}")
            tests = tests.replace("        survey['road_axis_xy'] = [2, 0]",
                                  "        survey['usps_official_business'] = False\n"
                                  "        with self.assertRaisesRegex(ValueError, 'USPS official-business'):\n"
                                  "            survey_check(survey)\n"
                                  "        survey['usps_official_business'] = True\n"
                                  "        survey['road_axis_xy'] = [2, 0]")
        (bundle / 'tests').mkdir(exist_ok=True)
        (bundle / 'tests/test_bundle.py').write_text(tests)
        names = ('runner.py', 'config.json', 'finalize.py', 'measure_driveway.py', 'tests/test_bundle.py')
        files = [{'path': name, 'content': ((HERE / name) if name == 'measure_driveway.py' else (bundle / name)).read_text()} for name in names]
        construction = {'format': 'worker-construction', 'assignment_id': AID,
                        'case_id': case, 'cell_id': 'C150094', 'law_id': 'LVMC-11-52-130-A7',
                        'actor': 'motor_vehicle_driver', 'entrypoint': 'runner.py',
                        'recording_description': config['recording_description'], 'files': files}
        path = HERE / ('selected-construction-probe_' + probe + '.json')
        write(path, construction)
        entries.append({'case_id': case, 'construction': path.name,
                        'construction_sha256': sha(path), 'candidate_risk': {
                            'status': 'none', 'reason': 'No original route or camera failure is measured for this exact comparison case'},
                        'candidates': []})
    write(HERE / 'selected-offline-manifest.json', {'assignment_id': AID, 'cases': entries})
    print(json.dumps({row['case_id']: row['construction_sha256'] for row in entries}, sort_keys=True))


if __name__ == '__main__':
    main()
