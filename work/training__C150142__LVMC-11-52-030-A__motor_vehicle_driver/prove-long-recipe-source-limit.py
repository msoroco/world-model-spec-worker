"""Probe the pinned fixture generator's long-source representation limits."""
import json
import os
from pathlib import Path

from worker_exchange.fixture_generator import generate, inspect


def rejected(spec):
    try:
        inspect(spec)
    except ValueError as error:
        return str(error)
    raise AssertionError('Unexpectedly accepted diagnostic output')


def main():
    repo = Path(__file__).resolve().parents[2]
    scratch = repo / '.runtime-work' / 'owner150142' / 'recipe-source-limit'
    scratch.mkdir(parents=True, exist_ok=True)
    root = {'files': {}, 'graphs': [], 'videos': []}
    video = {'path': 'overview.mkv', 'frames': 36120, 'width': 8,
             'height': 8, 'fps': 20, 'color': 'black'}
    graph = {'path': 'video_frames.jsonl', 'attributes': {},
             'nodes': [], 'edges': []}
    video_error = rejected({**root, 'videos': [video]})
    graph_error = rejected({**root, 'graphs': [graph]})
    assert 'Invalid bounded diagnostic video parameters' in video_error
    assert 'live adapter JSON format' in graph_error

    literal = '{"video_frame":0}\\n'
    output = scratch / 'literal-output'
    if output.exists():
        import shutil
        shutil.rmtree(output)
    generate({**root, 'files': {'video_frames.jsonl': literal}}, output)
    actual = (output / 'video_frames.jsonl').read_bytes()
    assert actual == literal.encode('utf-8')

    frozen_large = []
    for dirname in ('inputs', 'runtime'):
        for path in (repo / dirname).rglob('*'):
            if path.is_file() and path.stat().st_size > 2 * 1024 * 1024:
                frozen_large.append(str(path.relative_to(repo)))
    assert not frozen_large, frozen_large[:10]
    receipt = {
        'format': 'c150142-long-recipe-source-limit-v1',
        'case_id': 'training__C150142__LVMC-11-52-030-A__motor_vehicle_driver__tour_bus_below',
        'frames': 36120,
        'generator_long_video_error': video_error,
        'generator_frame_map_graph_error': graph_error,
        'file_text_written_literally': True,
        'frozen_source_files_over_2mib': frozen_large,
        'scratch_output_under_runtime_work': str(output.relative_to(repo)),
        'source_reuse_available_from_frozen_inputs': False,
        'conclusion': 'No pinned generator mode expands a compact specification into the required full-frame video_frames.jsonl; no frozen input or runtime file supplies a source larger than 2 MiB.',
        'limitation': 'This is a fixture-interface probe, not an official positive or negative compatibility receipt.'
    }
    destination = Path(__file__).with_name('current-long-recipe-source-limit.json')
    destination.write_text(json.dumps(receipt, sort_keys=True, indent=2) + '\n')
    print(json.dumps({'receipt': str(destination.relative_to(repo)),
                      'frozen_large_count': len(frozen_large),
                      'long_video_rejected': True,
                      'frame_map_graph_rejected': True,
                      'literal_file_confirmed': True}, sort_keys=True))


if __name__ == '__main__':
    if '.runtime-work' not in os.environ.get('SCENARIO_PIPELINE_OUTPUT_ROOT', ''):
        raise SystemExit('Set SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work')
    main()
