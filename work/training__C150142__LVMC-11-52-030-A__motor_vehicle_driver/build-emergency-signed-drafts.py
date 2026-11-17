"""Derive exact signed emergency candidates from the unsigned CPU drafts."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'native'))
from exception_road import construct, readback

SIGN = ['armored_or_emergency']


def encoded(value):
    return json.dumps(value, indent=2, allow_nan=False) + '\n'


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def signed_runner(source):
    source = source.replace("authored['sign_readback']['present'] or", "not authored['sign_readback']['present'] or")
    source = source.replace('Unsigned business curb construction differs', 'Signed business curb construction differs')
    source = source.replace('Unsigned curb construction differs from exact case', 'Signed curb construction differs from exact case')
    start = source.index('        if native_signs or authored[\'sign_readback\'][\'present\']:')
    end = source.index("        (output / 'native-map-readback.json').write_text", start)
    source = source[:start] + (
        "        if len(native_signs) != 1 or abs(float(native_signs[0].get('s'))-40) > .01 or \\\n"
        "           abs(float(native_signs[0].get('t'))+7.5) > .01:\n"
        "            raise RuntimeError('Native signed-curb signal readback differs')\n") + source[end:]
    source = source.replace("'sign_readback': authored['sign_readback'],", "'sign_readback': {**authored['sign_readback'],\n"
        "                'native_signal_id': native_signs[0].get('id'),\n"
        "                'native_signal_s_m': float(native_signs[0].get('s')),\n"
        "                'native_signal_t_m': float(native_signs[0].get('t')),\n"
        "                'classes_source': 'authored OpenDRIVE userData; pixels unreviewed'},")
    return source


def signed_finalizer(source):
    source = source.replace('unsigned emergency no-worker', 'signed emergency no-worker')
    source = source.replace("if sign != authored['sign_readback'] or sign.get('present'):\n"
        "        raise ValueError('Missing source-bound unsigned-curb readback')", "if sign != authored['sign_readback'] and not (\n"
        "        isinstance(sign, dict) and\n"
        "        {key: sign.get(key) for key in authored['sign_readback']} ==\n"
        "            authored['sign_readback'] and\n"
        "        map_readback.get('source_kind') == 'native_readback' and\n"
        "        sign.get('native_signal_id') == '15014201'):\n"
        "        raise ValueError('Missing source-bound signed-curb readback')")
    return source


def build():
    matrix = json.loads((ROOT / 'exception-case-matrix.json').read_text())
    output = []
    for suffix in ('business', 'no_business'):
        old = 'emergency_vehicle_unsigned_' + suffix
        new = 'emergency_vehicle_signed_' + suffix
        case_id = ROOT.name + '__' + new
        case = next(row for row in matrix['cases'] if row['case_id'] == case_id)
        expected_activity = 'business_activity' if suffix == 'business' else None
        if (case['sign_classes'], case['activity_request'], case['mailbox_requested']) != (SIGN, expected_activity, False):
            raise ValueError('Signed emergency matrix differs')
        road = construct(case)
        if readback(road)['sign_readback']['displayed_classes'] != SIGN:
            raise ValueError('Signed road readback differs')
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            prefix = ROOT / ('selected-primary' if candidate == 'primary' else 'selected-fallbacks')
            old_path = prefix / old
            new_path = prefix / new
            if candidate != 'primary':
                old_path /= candidate
                new_path /= candidate
            package = json.loads((old_path / 'construction.json').read_text())
            files = {row['path']: row['content'] for row in package['files']}
            config = json.loads(files['config.json'])
            if config['sign_classes'] or config['service_class'] != 'emergency_vehicle':
                raise ValueError('Unsigned draft source differs')
            config.update(case_id=case_id, selected_case_id=case_id,
                          supported_case_ids=[case_id], sign_classes=SIGN,
                          road_sha256=digest(road))
            files['config.json'] = encoded(config)
            files['red-curb-road.xodr'] = road
            files['runner.py'] = signed_runner(files['runner.py'])
            files['finalize_selected.py'] = signed_finalizer(files['finalize_selected.py'])
            files['tests/test_selected.py'] = files['tests/test_selected.py'].replace("self.assertEqual(cfg['sign_classes'], [])", "self.assertEqual(cfg['sign_classes'], ['armored_or_emergency'])").replace("['sign_classes'], []", "['sign_classes'], ['armored_or_emergency']")
            package['case_id'] = case_id
            package['files'] = [{'path': path, 'content': content} for path, content in files.items()]
            package['measurement_plan']['source'] = package['measurement_plan']['source'].replace('unsigned red-curb', 'signed red-curb')
            package['recording_description']['limitations'][-1] += ' The authored sign and Native signal require physical text and visibility review.'
            new_path.mkdir(parents=True, exist_ok=True)
            target = new_path / 'construction.json'
            target.write_text(encoded(package))
            output.append({'case_id': case_id, 'candidate': candidate,
                           'construction': str(target.relative_to(ROOT)),
                           'sha256': digest(target.read_text()),
                           'original_native_observed': False})
    return output


if __name__ == '__main__':
    print(encoded(build()), end='')
