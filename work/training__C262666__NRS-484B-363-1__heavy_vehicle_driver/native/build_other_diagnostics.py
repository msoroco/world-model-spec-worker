"""Derive seven explicit diagnostic source recipes for exact school-zone branches."""
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
REPO = ROOT.parents[1]
AID = ROOT.name
SPECS = {
    'probe_01': (14, {}),
    'probe_02': (15, {}),
    'probe_04': (17, {'school_session_day': False}),
    'probe_05': (17, {'half_hour_window_exception': True}),
    'probe_06': (17, {'beacon_flashing': False}),
    'probe_07': (17, {'beacon_operational': False, 'nonbeacon_sign_in_effect': True}),
    'probe_08': (17, {'beacon_operational': False, 'nonbeacon_sign_in_effect': False}),
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def lines(text):
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def encode(rows):
    return ''.join(json.dumps(row, separators=(',', ':'), allow_nan=False) + '\n' for row in rows)


def main():
    template = json.loads((HERE/'selected-generator-probe_03.json').read_text())
    base = template['files']
    for suffix, (mph, updates) in SPECS.items():
        case = AID+'__'+suffix
        spec = copy.deepcopy(template)
        files = spec['files']
        context = json.loads(base['school_zone_context.json'])
        context['case_id'] = case
        context.update(updates)
        files['school_zone_context.json'] = json.dumps(context, separators=(',', ':'))+'\n'
        speed = mph * .44704
        offset = 40.0 if mph <= 15 else 0.0
        motion, trace, evidence = (lines(base[name]) for name in
                                   ('native_motion.jsonl', 'trace.jsonl', 'capture/evidence.jsonl'))
        for i, (sample, core, sensor) in enumerate(zip(motion, trace, evidence)):
            y = round(offset + i * speed / 20, 7)
            sample.update(ego_y_m=y, velocity_y_mps=speed)
            core['position']['y'] = y
            core['position_m'][1] = y
            core['speed_mps'] = speed
            core['speed_mph'] = mph
            core['velocity_mps'][1] = speed
            sensor['ego']['position_m'][1] = y
            sensor['ego']['speed_mps'] = speed
            sensor['ego']['body_vertices_m'] = [[point[0], y + (2.0 if point[1] > 0 else -2.0), point[2]]
                for point in [[1.0,-1,0],[1.0,-1,1.5],[2.5,-1,0],[2.5,-1,1.5],
                              [2.5,1,0],[2.5,1,1.5],[1.0,1,0],[1.0,1,1.5]]]
            sensor['world']['road_projection']['s_m'] = y
        for name, data in (('native_motion.jsonl', motion), ('trace.jsonl', trace),
                           ('capture/evidence.jsonl', evidence)):
            files[name] = encode(data)
        manifest = json.loads(base['capture/manifest.json'])
        manifest['sources']['trace.jsonl'] = hashlib.sha256(files['trace.jsonl'].encode()).hexdigest()
        files['capture/manifest.json'] = json.dumps(manifest, separators=(',', ':'))+'\n'
        spec_path = HERE/('selected-generator-'+suffix+'.json')
        spec_path.write_text(json.dumps(spec, separators=(',', ':'))+'\n')
        anchor = HERE/('diagnostic-anchor-'+suffix+'.json')
        anchor.write_text(json.dumps({'assignment_id': AID, 'case_id': case,
            'scope': 'synthetic diagnostic only'}, separators=(',', ':'))+'\n')
        recipe = {'format': 'worker-fixture-recipe',
                  'sources': [{'path': 'diagnostic-anchor.json',
                               'source': str(anchor.relative_to(REPO)), 'sha256': sha(anchor)}],
                  'generator': {'source': str(spec_path.relative_to(REPO)), 'sha256': sha(spec_path)}}
        recipe_path = HERE/('selected-recipe-'+suffix+'.json')
        recipe_path.write_text(json.dumps(recipe, indent=2)+'\n')
        contract = json.loads((HERE/'measurement-probe_03.json').read_text())
        contract['case_id'] = case
        (HERE/('measurement-'+suffix+'.json')).write_text(json.dumps(contract, indent=2)+'\n')
        print(suffix, spec_path.stat().st_size, sha(spec_path))


if __name__ == '__main__':
    main()
