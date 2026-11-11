"""Materialize the canonical root entrypoint from the selected primary bundle."""
import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT/'native/package-current/reference/primary/construction.json'


def write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def main():
    package = json.loads(SOURCE.read_text())
    config_item = next(item for item in package['files']
                       if item['path'] == 'config.json')
    config = json.loads(config_item['content'])
    config['cameras'] = [
        {'name':'overview','width':1920,'height':1080,'pose_strategy':'fixed_elevated_arc',
         'fov_deg':85},
        {'name':'approach','width':1280,'height':720,'pose_strategy':'fixed_entry',
         'fov_deg':90},
        {'name':'reference_corner','width':1280,'height':720,
         'pose_strategy':'fixed_exit_corner','fov_deg':90},
        {'name':'driver_reference','width':1280,'height':720,
         'pose_strategy':'ego_attached','fov_deg':90}]
    config_item['content'] = json.dumps(config, indent=2)+'\n'
    runner = (ROOT/'runner.py').read_text()
    package['files'] = copy.deepcopy(package['files'])
    bundled = next((item for item in package['files'] if item['path']=='runner.py'),None)
    if bundled is None:
        package['files'].append({'path':'runner.py','content':runner})
    elif bundled['content'] != runner:
        raise ValueError('Bundled Native runner differs from root entrypoint')
    package['entrypoint'] = 'runner.py'
    plan = json.loads((ROOT/'case-plan.json').read_text())
    package['measurement_plan'] = {
        'case_id':package['case_id'],
        'requirements':plan['requirement_dispositions'],
        'source':'native/measurement-contracts-current/reference.json'}
    for item in package['files']:
        write(ROOT/item['path'], item['content'])
    write(ROOT/'construction.json', json.dumps(package,indent=2)+'\n')
    print(json.dumps({'case_id':package['case_id'],
                      'files':len(package['files']),
                      'entrypoint':package['entrypoint']}))


if __name__ == '__main__':
    main()
