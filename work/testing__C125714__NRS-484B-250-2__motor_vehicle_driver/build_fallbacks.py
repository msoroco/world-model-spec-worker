"""Author alternate spawn waypoint candidates for exact physical spawn risk."""
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    folder = Path(__file__).resolve().parent
    manifest_path = folder / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest['cases']:
        case = entry['case_id'].split('__')[-1]
        source = folder / entry['construction']
        construction = json.loads(source.read_text())
        scene_entry = next(item for item in construction['files'] if item['path'] == 'scene.json')
        scene = json.loads(scene_entry['content'])
        old = scene['ego_route_xyz_m'][0]
        assert old == [-25, -4, 0]
        scene['ego_route_xyz_m'][0] = [-23, -4, 0]
        scene['fallback_spawn'] = {
            'candidate_id': 'fallback1',
            'primary_first_waypoint_xyz_m': old,
            'alternate_first_waypoint_xyz_m': [-23, -4, 0],
            'trigger': 'first reviewed route waypoint spawn failure',
            'scope': 'engineering alternative; reviewed physical route required'}
        scene_entry.pop('source', None)
        scene_entry['content'] = json.dumps(scene, indent=2, allow_nan=False) + '\n'
        candidate = folder / 'cases' / case / 'fallback1-construction.json'
        candidate.write_text(json.dumps(construction, indent=2, allow_nan=False) + '\n')
        entry['candidates'] = [{'id': 'fallback1',
            'construction': str(candidate.relative_to(folder)),
            'construction_sha256': sha(candidate),
            'trigger': {'source': 'Native owner capture log and route waypoint readback',
                        'metric': 'first reviewed ego route waypoint spawn result',
                        'failure_condition': 'primary ego first-waypoint spawn returns no actor'},
            'changed_knobs': ['ego first route waypoint x from -25 m to -23 m on the same authored approach road'] }]
        entry['candidate_risk'] = {'status': 'physical',
            'reason': 'Two-vehicle median-opening spawn and crossing can fail at the first route waypoint; alternate nearby approach waypoint retains the exact case and observation channels.'}
        print(case, sha(candidate))
    manifest_path.write_text(json.dumps(manifest, indent=2, allow_nan=False) + '\n')


if __name__ == '__main__':
    main()
