"""Rebuild the two official inline cases against the current Native binding."""

import json
from hashlib import sha256
from pathlib import Path


HERE = Path(__file__).resolve().parent


def replace_once(source, old, new):
    if source.count(old) != 1:
        raise ValueError(f"Expected one occurrence of {old!r}")
    return source.replace(old, new)


def green_runner(official):
    source = replace_once(official, "__official_device_control'", "__official_device_green_phase'")
    source = replace_once(
        source,
        "    if config.get('yield_clearance_m', 0) <= 0:",
        "    if config.get('desired_signal_state') != 'Green':\n"
        "        raise ValueError('Exact Green device phase missing')\n"
        "    if config.get('yield_clearance_m', 0) <= 0:",
    )
    source = replace_once(
        source, "    actors, sinks = [], {}\n",
        "    actors, sinks = [], {}\n    selected_signal = signal_previous_state = None\n",
    )
    source = replace_once(
        source,
        "        device_recorder = DeviceSourceRecorder(output, selected_device, routes['junction_id'])\n",
        "        device_recorder = DeviceSourceRecorder(output, selected_device, routes['junction_id'])\n"
        "        selected_signal = selected_device[0]\n"
        "        signal_previous_state = selected_signal.get_state()\n"
        "        selected_signal.set_state(carla.TrafficLightState.Green)\n",
    )
    source = replace_once(
        source, "        for _ in range(config['frames']):\n",
        "        for _ in range(config['frames']):\n"
        "            selected_signal.set_state(carla.TrafficLightState.Green)\n",
    )
    source = replace_once(
        source, "    finally:\n        if frame_map is not None:",
        "    finally:\n"
        "        if selected_signal is not None and signal_previous_state is not None:\n"
        "            selected_signal.set_state(signal_previous_state)\n"
        "        if frame_map is not None:",
    )
    return source


def update():
    official = (HERE / 'ending_road_official_runner.py').read_text()
    green = green_runner(official)
    (HERE / 'ending_road_green_runner.py').write_text(green)
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    entries = {case['case_id'].rsplit('__', 1)[-1]: case for case in manifest['cases']}
    for kind, primary in (
        ('official_device_control', 'construction-official-device.json'),
        ('official_device_green_phase', 'construction-official-green.json'),
    ):
        entry = entries[kind]
        fallback_stem = 'official_green_phase' if kind == 'official_device_green_phase' else kind
        for candidate, filename in [('', primary)] + [
            (f'fallback{i}', f'construction-{fallback_stem}-fallback{i}.json') for i in (1, 2, 3)
        ]:
            path = HERE / filename
            construction = json.loads(path.read_text())
            files = {item['path']: item for item in construction['files']}
            runner = official if kind == 'official_device_control' else green
            if candidate == 'fallback1':
                runner = replace_once(
                    runner, 'select_t_routes(world.get_map(), route_accept=',
                    'select_t_routes(world.get_map(), max_spawns=600, route_accept=',
                )
            if candidate == 'fallback2':
                runner = replace_once(runner, '.22 * (speed_mps - speed)', '.18 * (speed_mps - speed)')
            files['runner.py']['content'] = runner
            for module in ('official_geometry_binding.py', 'official_geometry_preflight.py'):
                content = (HERE / module).read_text()
                if module in files:
                    files[module]['content'] = content
                else:
                    construction['files'].append({'path': module, 'content': content})
            path.write_text(json.dumps(construction, indent=2) + '\n')
            digest = sha256(path.read_bytes()).hexdigest()
            target = entry if not candidate else next(x for x in entry['candidates'] if x['id'] == candidate)
            target['construction_sha256'] = digest
            target['offline']['construction_sha256'] = digest
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    update()
