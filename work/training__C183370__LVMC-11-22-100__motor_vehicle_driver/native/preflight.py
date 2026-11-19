"""Run the C183370 live-map/person preflight before an original capture."""
import argparse
import json
from pathlib import Path

from live_readback import bind
from pathing import repository_root


def run(survey_path, output_path, client, carla):
    repo = repository_root(__file__)
    output = Path(output_path).resolve()
    generated = (repo / '.runtime-work').resolve()
    if not output.is_relative_to(generated):
        raise ValueError('Generated Native readback must stay under .runtime-work')
    if output.exists():
        raise ValueError('Preserve the previous live readback; choose a new output')
    survey = json.loads(Path(survey_path).read_text())
    receipt = bind(survey, client.get_world(), carla)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n')
    return receipt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--survey', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    import carla
    client = carla.Client(args.host, args.port)
    client.set_timeout(10.0)
    run(args.survey, args.output, client, carla)


if __name__ == '__main__':
    main()
