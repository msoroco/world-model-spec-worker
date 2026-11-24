"""Local CARLA CLI for exact three-vehicle reciprocal left-turn capture.

This wires the separately spawned later opponent and four cameras into the
source-reviewed reciprocal runner. Physical and legal outcomes stay unresolved.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from bundle_runner import check


def run_native(config_path, map_path, output_dir, host='127.0.0.1', port=2000,
               *, api=None, client=None):
    config = json.loads(Path(config_path).read_text(encoding='utf-8'))
    packet = json.loads(Path(map_path).read_text(encoding='utf-8'))
    if packet.get('diagnostic_fixture') or packet.get('reviewed_original_map') is not True:
        raise ValueError('production reciprocal capture requires reviewed original Native map')
    request = check(config, packet)
    if request['controller']['wait_for_later_opponent'] is None:
        raise ValueError('exact reciprocal case with separate later opponent required')
    if request['case_id'].rsplit('__', 1)[-1] not in ('reciprocal_yield', 'reciprocal_no_yield'):
        raise ValueError('exact reciprocal case required')
    output = Path(output_dir)
    if output.exists() and any(output.iterdir()):
        raise ValueError('Native attempt output must be empty')
    if api is None:
        import carla as api
    if client is None:
        client = api.Client(host, int(port))
        client.set_timeout(30.0)
    from reciprocal_live import make_scene_factory, run
    return run(client=client, config_path=config_path, map_path=map_path,
               output=output, scene_factory=make_scene_factory(api),
               location_factory=lambda x, y: api.Location(x=x, y=y),
               left_blinker_mask=int(api.VehicleLightState.LeftBlinker))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    parser.add_argument('--map-packet', required=True)
    parser.add_argument('--output-dir', required=True)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args(argv)
    result = run_native(args.config, args.map_packet, args.output_dir,
                        args.host, args.port)
    print(json.dumps(result, default=str))


if __name__ == '__main__':
    main()
