"""Create a camera coverage fallback for each selected qualitative case."""
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CASES = {
    'stop_opposite_straight': 'straight',
    'stop_ego_left_near_time_no_device': 'absent',
}


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    manifest_path = HERE / 'execution-manifest.json'
    manifest = read(manifest_path)
    for suffix, stem in CASES.items():
        entry = next(row for row in manifest['cases'] if row['case_id'] == HERE.name + '__' + suffix)
        primary = read(HERE / entry['construction'])
        files = {row['path']:row for row in primary['files']}
        site = json.loads(files['site.json']['content'])
        overview = site['camera_poses']['overview']
        if not isinstance(overview, list) or len(overview) != 6:
            raise ValueError('Expected sourced overview pose')
        site = copy.deepcopy(site)
        site['camera_poses']['overview'][0] += 2.0
        site_path = HERE / (stem + '-fallback1-site.json')
        write(site_path, site)
        config = json.loads(files['config.json']['content'])
        config['site_packet']['sha256'] = sha(site_path)
        config_path = HERE / (stem + '-fallback1-config.json')
        write(config_path, config)
        fallback = copy.deepcopy(primary)
        for item in fallback['files']:
            if item['path'] in ('site.json', 'config.json'):
                source = site_path if item['path'] == 'site.json' else config_path
                item['source'] = str(source.relative_to(ROOT))
                item['content'] = source.read_text()
        fallback['case_design'] = copy.deepcopy(primary.get('case_design', {}))
        fallback['case_design']['fallback_overview_camera_shift_m'] = 2.0
        fallback['case_design']['physical_acceptance_claimed'] = False
        path = HERE / (stem + '-fallback1-construction.json')
        write(path, fallback)
        candidate = {
            'id':'fallback1', 'construction':path.name,
            'construction_sha256':sha(path),
            'trigger':{'source':'original overview.mkv and video_frames.jsonl',
                       'metric':'overview body/device visibility at crossing entry',
                       'failure_condition':'Overview misses a required body-entry or device frame'},
            'changed_knobs':['site.camera_poses.overview.x'],
            'remedy':'Shift overview source camera 2 m while retaining exact case identity, timing, actors and recording contract',
        }
        entry['candidates'] = [candidate]
    write(manifest_path, manifest)
    print(json.dumps({'fallbacks':len(CASES),
                      'manifest_sha256':sha(manifest_path)},sort_keys=True))


if __name__ == '__main__':
    build()
