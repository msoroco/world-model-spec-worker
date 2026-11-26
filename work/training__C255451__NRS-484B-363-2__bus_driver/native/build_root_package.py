"""Materialize the exact eight-case root dispatch and camera/source plan."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT.parents[1]
PLAN = ROOT / 'case-plan.json'
MANIFEST = ROOT / 'execution-manifest.json'
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def build():
    manifest = json.loads(MANIFEST.read_text())
    case_ids = [entry['case_id'] for entry in manifest['cases']]
    source = json.loads((ROOT / 'native/selected_primary/config.json').read_text())
    for key in ('case_id', 'selected_case_id', 'candidate_id', 'target_mph', 'planned_context', 'case'):
        source.pop(key, None)
    source['supported_case_ids'] = case_ids
    for camera in source['cameras']:
        camera['pose_strategy'] = 'surveyed fixed world transform with installed sign and full crossing interval in source view'
        camera['fov_deg'] = 80
    config = ROOT / 'config.json'
    config.write_text(json.dumps(source, indent=2) + '\n')
    plan = json.loads(PLAN.read_text())
    plan['observations'] = [{
        'name': 'school_crossing_observation', 'mandatory': True,
        'source_note': '600 joined Native bus velocity, zone station and original road direction frames',
        'status': 'selected_native_and_saved_finalizer'}]
    channels = {
        'dev.zone_sign': ['school_crossing_observation'],
        'drv.within_signed_zone': ['school_crossing_observation'],
        'kin.speed': ['school_crossing_observation'],
        'dev.speed_limit_beacon': [],
        'drv.condition_in_effect': [],
        'env.civil_time': [],
        'ru.motor_vehicle': ['school_crossing_observation'],
    }
    for term, item in plan['source_observation_mapping'].items():
        item['channels'] = channels[term]
        item['evidence'] = ('Selected measured Native motion channel plus independently reviewed original '
                            'designation, sign, school calendar, civil clock, beacon phase and vehicle source '
                            'as applicable; no Core atom or legal verdict is asserted.')
        item['source_refs'] = ['inputs/' + ROOT.name + '/assignment.json']
    plan['camera_plan'] = {
        'profile': 'overview1080-capability', 'duration_s': 30,
        'composition': 'synchronized_four_view_primary',
        'coverage': [
            {'view': 'overview', 'subject': 'bus, children, crossing-zone sign and full zone interval', 'interval': '0-30 s'},
            {'view': 'approach', 'subject': 'bus approach, crossing sign and beacon lamp state', 'interval': '0-30 s'},
            {'view': 'reference_corner', 'subject': 'crossing geometry, sign face and children', 'interval': '0-30 s'},
            {'view': 'driver_reference', 'subject': 'bus motion and driver road direction', 'interval': '0-30 s'}],
        'source_review': 'Pixel visibility and official designation are independent local original-source checks',
    }
    PLAN.write_text(json.dumps(plan, indent=2) + '\n')
    runner = ROOT / 'runner.py'
    runner.write_text('"""Exact-case dispatch preflight; selected Native runners own acquisition."""\n'
                      'import argparse\nimport json\nfrom pathlib import Path\n'
                      'ROOT = Path(__file__).resolve().parent\n'
                      'def check(case):\n'
                      '    manifest = json.loads((ROOT / "execution-manifest.json").read_text())\n'
                      '    config = json.loads((ROOT / "config.json").read_text())\n'
                      '    cases = {item["case_id"] for item in manifest["cases"]}\n'
                      '    if case not in cases or cases != set(config["supported_case_ids"]):\n'
                      '        raise ValueError("Select an exact prepared bus school-crossing case")\n'
                      '    return {"case_id": case, "frames": 600, "rate_hz": 20,\n'
                      '            "physical_acceptance_claimed": False}\n'
                      'if __name__ == "__main__":\n'
                      '    parser = argparse.ArgumentParser()\n'
                      '    parser.add_argument("--case", required=True)\n'
                      '    args = parser.parse_args()\n'
                      '    print(json.dumps(check(args.case), sort_keys=True))\n')
    construction = {
        'format': 'worker-inline-construction', 'law_id': 'NRS-484B-363-2',
        'cell_id': 'C255451', 'actor': 'bus_driver', 'entrypoint': 'runner.py',
        'files': [{'path': 'runner.py', 'source': str(runner.relative_to(REPO)), 'content': runner.read_text()},
                  {'path': 'config.json', 'source': str(config.relative_to(REPO)), 'content': config.read_text()}],
        'measurement_plan': {'entrypoint': 'native/measure_saved.py', 'required_sources':
                             ['native_motion.jsonl', 'school_zone_context.json', 'video_frames.jsonl'],
                             'status': 'source_bound_saved_measurement'},
        'recording_description': source['recording_description'],
        'static_checks': ['exact eight-case dispatch', '25 mph statute', '600 joined source frames',
                          'four source cameras', 'surveyed installed sign/beacon geometry'],
        'termination_rules': ['600 frames at 20 Hz', 'encoders closed and world restored before saved processing'],
        'mechanisms': ['survey-gated original CARLA source acquisition',
                       'source-bound saved meter and finalizer', 'independent source review'],
    }
    (ROOT / 'construction.json').write_text(json.dumps(construction, indent=2) + '\n')
    print('root dispatch, capture profile and source mapping ready for CPU tests')


if __name__ == '__main__':
    build()
