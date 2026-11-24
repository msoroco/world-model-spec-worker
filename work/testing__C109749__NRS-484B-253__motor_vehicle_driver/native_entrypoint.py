"""Local CARLA entrypoint for the six exact two-vehicle left-turn cases."""
from __future__ import annotations

import json
from pathlib import Path

from bundle_runner import check


def run_native(config_path, map_path, output_dir, host='127.0.0.1', port=2000,
               *, api=None, client=None):
    config = json.loads(Path(config_path).read_text(encoding='utf-8'))
    packet = json.loads(Path(map_path).read_text(encoding='utf-8'))
    if packet.get('diagnostic_fixture') or packet.get('reviewed_original_map') is not True:
        raise ValueError('production capture requires reviewed original Native map')
    request = check(config, packet)
    if request['controller']['wait_for_later_opponent'] is not None:
        raise ValueError('two-vehicle entrypoint rejects reciprocal case')
    output = Path(output_dir)
    if output.exists() and any(output.iterdir()):
        raise ValueError('Native attempt output must be empty')
    if api is None:
        import carla as api
    if client is None:
        client = api.Client(host, int(port))
        client.set_timeout(30.0)
    from carla_scene_factory import make_scene_factory
    from live_capture import run
    return run(client=client, config_path=config_path, map_path=map_path,
               output=output, scene_factory=make_scene_factory(api),
               location_factory=lambda x, y: api.Location(x=x, y=y),
               left_blinker_mask=int(api.VehicleLightState.LeftBlinker))
