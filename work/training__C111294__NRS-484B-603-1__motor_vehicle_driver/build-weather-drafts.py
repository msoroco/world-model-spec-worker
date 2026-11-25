"""Build separate same-cell wet-weather construction drafts from controlled pair."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PAIRS = (('probe_a', 'weather_probe_a'), ('probe_b', 'weather_probe_b'))


def revise(text):
    for old, new in PAIRS:
        text = text.replace(old, new)
    return text


def build(old, new):
    source = HERE / f'current-v2-{old}-diagnostic/construction.json'
    construction = json.loads(source.read_text())
    construction['case_id'] = revise(construction['case_id'])
    for entry in construction['files']:
        path = entry['path']
        content = revise(entry['content'])
        if path == 'runner.py':
            clear = 'world.set_weather(carla.WeatherParameters.ClearNoon)'
            wet = '''weather = carla.WeatherParameters.WetCloudyNoon
        world.set_weather(weather)
        observed_weather = world.get_weather()'''
            if clear not in content:
                raise ValueError('Weather control anchor absent')
            content = content.replace(clear, wet)
            content = content.replace('"territorial_applicability_verified": False})',
                '"territorial_applicability_verified": False,\n'
                '            "weather_parameters": {"preset": "WetCloudyNoon",\n'
                '                "precipitation": observed_weather.precipitation,\n'
                '                "wetness": observed_weather.wetness}})')
        if path == 'engineering.py':
            pass
        if path == 'finalize.py':
            marker = '\ndef finalize(folder: Path, contract: dict, expected_source_sha256: str) -> dict:\n'
            extra = '''

def measure_weather_approach(folder: Path, value: dict) -> dict:
    context = json.loads(_required(folder, "context.json").read_text())
    weather = context.get("weather_parameters", {})
    if not isinstance(weather.get("wetness"), (int, float)) or weather["wetness"] <= 0:
        raise ValueError("Missing source-bound wet highway condition")
    evidence = _rows(folder, "capture/evidence.jsonl")
    if len(evidence) != 600 or any(row.get("world", {}).get("weather", {}).get("wetness", 0) <= 0 for row in evidence):
        raise ValueError("Wet highway condition missing from frame evidence")
    return dict(value, weather_parameters=weather, weather_frame_count=len(evidence),
                weather_necessity_legally_verified=False)
'''
            if marker not in content:
                raise ValueError('Weather measurement insertion anchor absent')
            content = content.replace(marker, extra + marker, 1)
            content = content.replace('value = measure_intersection_approach(rows, relation, road)',
                                      'value = measure_weather_approach(folder, measure_intersection_approach(rows, relation, road))')
            content = content.replace('req["output_key"] != "intersection_approach" or req["method"] != "measure_intersection_approach"',
                                      'req["output_key"] != "weather_approach" or req["method"] != "measure_weather_approach"')
            content = content.replace('report["measurements"]["intersection_approach"]["value"]',
                                      'report["measurements"]["weather_approach"]["value"]')
        if path == 'measurement-contract.json':
            data = json.loads(content)
            row = data['requirements'][0]
            row['disposition_index'] = 5
            row['output_key'] = 'weather_approach'
            row['method'] = 'measure_weather_approach'
            row['inputs'] = ['native_samples.jsonl', 'road.xodr', 'context.json', 'capture/evidence.jsonl']
            content = json.dumps(data, indent=2) + '\n'
        if path == 'config.json':
            data = json.loads(content)
            data['supported_case_ids'] = [HERE.name + '__' + new]
            data['weather_preset'] = 'WetCloudyNoon'
            data['recording_description']['context_inputs'].append({
                'name': 'weather_parameters', 'unit': 'structured',
                'method': 'original Native CARLA world weather readback'})
            content = json.dumps(data, indent=2) + '\n'
            construction['recording_description'] = data['recording_description']
        if path == 'draft-candidates.json':
            data = json.loads(content)
            content = json.dumps(data, indent=2) + '\n'
        entry['content'] = content
    target = HERE / 'weather-branch-drafts' / new
    target.mkdir(parents=True, exist_ok=True)
    (target / 'construction.json').write_text(json.dumps(construction, indent=2) + '\n')
    for entry in construction['files']:
        if entry.get('source'):
            continue
        path = target / entry['path']
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(entry['content'])
    return target


if __name__ == '__main__':
    for old, new in PAIRS:
        print(build(old, new))
