"""Keep the four-camera capture fixed while making fallback 3 a speed-control alternative."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
TRIGGER = {'metric': 'max_reverse_heading_rate_deg_s', 'op': '>', 'threshold': 12,
           'source': 'original frame-joined Native pose and surveyed reverse route',
           'failure_condition': 'max_reverse_heading_rate_deg_s > 12'}


def replace(text, old, new):
    if old not in text:
        raise ValueError('Expected fallback 3 code fragment absent: ' + old)
    return text.replace(old, new)


def repair_bundle(path):
    bundle = json.loads(path.read_text())
    for item in bundle['files']:
        code = item['content']
        if item['path'] == 'engineering.py':
            code = replace(code, "'fallback3':{'overview_fov_deg':105}",
                           "'fallback3':{'target_reverse_speed_m_s':.7}")
            code = replace(code,
                           "'fallback3':{'metric':'min_reverse_body_pixel_margin_px','op':'<','threshold':40,\n              'source':'decoded original overview video and body mask'}",
                           "'fallback3':{'metric':'max_reverse_heading_rate_deg_s','op':'>','threshold':12,\n              'source':'original frame-joined Native pose and surveyed reverse route'}")
            code = replace(code,
                           "ReverseKnobs(steering_gain=knobs['steering_gain'],brake_margin_m=knobs['brake_margin_m'])",
                           "ReverseKnobs(steering_gain=knobs['steering_gain'],brake_margin_m=knobs['brake_margin_m'],target_reverse_speed_m_s=knobs.get('target_reverse_speed_m_s',1.0))")
        elif item['path'] == 'cameras.py':
            code = replace(code, "105 if candidate=='fallback3' else 90", '90')
        elif item['path'] == 'config.json':
            config = json.loads(code)
            config['engineering_knobs']['overview_fov_deg'] = 90
            config['engineering_knobs']['target_reverse_speed_m_s'] = 0.7
            for camera in config['cameras']:
                if camera['name'] == 'overview':
                    camera['fov_deg'] = 90
            code = json.dumps(config, indent=2) + '\n'
        elif item['path'] == 'tests/test_native.py':
            code = replace(code, "[{'steering_gain'},{'brake_margin_m'},{'overview_fov_deg'}]",
                           "[{'steering_gain'},{'brake_margin_m'},{'target_reverse_speed_m_s'}]")
        item['content'] = code
    path.write_text(json.dumps(bundle, indent=2) + '\n')
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    hashes = {}
    for suffix in ('condition_a', 'condition_b', 'condition_c'):
        path = HERE / 'cases' / suffix / 'fallback3/construction.json'
        hashes[suffix] = repair_bundle(path)
    for filename in ('current-base-proof-manifest.json', 'control-proof-manifest.json'):
        path = HERE / filename
        manifest = json.loads(path.read_text())
        for entry in manifest['cases']:
            suffix = {'false': 'condition_a', 'true': 'condition_b', 'control': 'condition_c'}[
                entry['case_id'].rsplit('__', 1)[-1]]
            fallback = next(c for c in entry['candidates'] if c['id'] == 'fallback3')
            fallback['construction_sha256'] = hashes[suffix]
            fallback['trigger'] = TRIGGER
            fallback['changed_knobs'] = ['target_reverse_speed_m_s']
        path.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps(hashes, indent=2))


if __name__ == '__main__':
    main()
