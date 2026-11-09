"""Deterministic diagnostic assets from text; never acquired physical evidence."""
import pickle
import subprocess
from pathlib import Path
from .common import within, sha

FORBIDDEN = {'case.json', 'config.json', 'construction.json', 'result.json',
             'analysis-report.json', 'compatibility.json'}


def inspect(spec):
    if not isinstance(spec, dict) or set(spec) != {'files', 'graphs', 'videos'}:
        raise ValueError('Diagnostic specification needs files, graphs and videos')
    if not isinstance(spec['files'], dict) or not isinstance(spec['graphs'], list) or not isinstance(spec['videos'], list):
        raise ValueError('Diagnostic files must be an object; graphs and videos must be lists')
    paths = []
    for path, value in spec['files'].items():
        if not isinstance(value, str):
            raise ValueError('Diagnostic files contain explicit UTF-8 text')
        paths.append(path)
    for graph in spec['graphs']:
        if set(graph) != {'path', 'attributes', 'nodes', 'edges'}:
            raise ValueError('Diagnostic graph needs path, attributes, nodes and edges')
        paths.append(graph['path'])
    for video in spec['videos']:
        if set(video) != {'path', 'frames', 'width', 'height', 'fps', 'color'}:
            raise ValueError('Diagnostic video needs path, frames, width, height, fps and color')
        if (any(type(video[k]) is not int or video[k] <= 0 for k in ('frames','width','height','fps'))
                or video['frames'] > 2000 or max(video['width'],video['height']) > 4096
                or video['fps'] != 20 or video['color'] not in ('black','white','red','green','blue')):
            raise ValueError('Invalid bounded diagnostic video parameters')
        paths.append(video['path'])
    if len(paths) != len(set(paths)):
        raise ValueError('Duplicate diagnostic output')
    for path in paths:
        within(Path('/tmp/diagnostic-path-validation'), path)
        if Path(path).parts[0] in FORBIDDEN:
            raise ValueError('Diagnostic cannot supply package configuration or outputs')
    return paths


def _graph(item):
    """Reconstruct diagnostic data without pickling version-specific NX internals."""
    import networkx as nx
    def attributes(value):
        if isinstance(value, dict):
            if set(value) == {'geometry_wkt'}:
                from shapely import wkt
                return wkt.loads(value['geometry_wkt'])
            return {k: attributes(v) for k, v in value.items()}
        if isinstance(value, list):
            return [attributes(v) for v in value]
        return value
    graph = nx.DiGraph()
    graph.graph.update(attributes(item['attributes']))
    for node in item['nodes']:
        graph.add_node(node['id'], **attributes(node['attributes']))
    for edge in item['edges']:
        graph.add_edge(edge['source'], edge['target'], **attributes(edge['attributes']))
    return graph


class _GraphInput:
    def __init__(self, item):
        self.item = item

    def __reduce__(self):
        from importlib import import_module
        return import_module('worker_exchange.fixture_generator')._graph, (self.item,)


def generate(spec, output):
    """Write inventoried text, simple graphs and lossless color frames; no scripts."""
    output = Path(output)
    paths = inspect(spec)
    if any(within(output, path).exists() for path in paths):
        raise ValueError('Diagnostic output shadows a source')
    for path, value in spec['files'].items():
        target = within(output, path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(value, encoding='utf-8')
    for item in spec['graphs']:
        target = within(output, item['path']); target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(pickle.dumps(_GraphInput(item), protocol=4))
    for item in spec['videos']:
        target = within(output, item['path']); target.parent.mkdir(parents=True, exist_ok=True)
        if target.suffix != '.mkv':
            raise ValueError('Diagnostic videos use lossless .mkv')
        subprocess.run(['ffmpeg','-nostdin','-hide_banner','-loglevel','error','-n',
            '-f','lavfi','-i',f"color=c={item['color']}:s={item['width']}x{item['height']}:r={item['fps']}",
            '-frames:v',str(item['frames']),'-an','-c:v','ffv1','-threads','1',
            '-fflags','+bitexact','-flags:v','+bitexact',str(target)],check=True,timeout=120)
    return {path: sha(within(output,path)) for path in sorted(paths)}
