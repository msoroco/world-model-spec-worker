"""Typed live graph projection for adapter consumption; never decodes pickles.

NetworkX contraction history, rendering caches and live waypoint handles are
deliberately outside this format. Lane geometry comes from source OpenDRIVE.
The original binary capture remains evidence, not an adapter input.
"""
import json
import math
from numbers import Integral, Real
from pathlib import Path

FORMAT = 'native-adapter-graph-v1'


def value(item):
    if item is None or isinstance(item, (str, bool)):
        return item
    if isinstance(item, Integral):
        return int(item)
    if isinstance(item, Real):
        number = float(item)
        if not math.isfinite(number):
            raise ValueError('Nonfinite native graph measurement')
        return number
    if isinstance(item, dict):
        if any(not isinstance(key, str) for key in item):
            raise ValueError('Native attribute keys must be strings')
        return {key: value(val) for key, val in item.items()}
    if isinstance(item, (list, tuple)):
        return [value(val) for val in item]
    if hasattr(item, 'tolist'):
        return value(item.tolist())
    raise ValueError('Unsupported native graph value: ' + str(type(item)))


def write(graph, path):
    nodes = list(graph)
    if any(not isinstance(node, (str, int)) or isinstance(node, bool) for node in nodes):
        raise ValueError('Native node identity must be a string or integer')
    indices = {node: index for index, node in enumerate(nodes)}
    records = []
    for node in nodes:
        attrs = {}
        for key, item in graph.nodes[node].items():
            if key in ('waypoint_obj', 'vertex_point', 'waypoint_bbox_polygon', 'contraction'):
                continue
            # CARLA signal enums have a stable named indication. Other opaque
            # objects must be handled explicitly before capture is accepted.
            if key in ('light_state', 'waypoint_lane_change', 'landmark_orientation'):
                item = str(item)
            # SGG marks undefined branch/end-point turn abstractions as NaN.
            # Preserve that unknown explicitly; never coerce it to a measurement.
            if key in ('angle', 'curve') and isinstance(item, Real) and math.isnan(float(item)):
                item = None
            attrs[key] = value(item)
        records.append({'id': node, 'attributes': attrs})
    payload = {'format': FORMAT, 'multigraph': graph.is_multigraph(),
               'metadata': {key: value(graph.graph[key]) for key in
                            ('frame', 'simulation_time_s', 'units', 'observed_evidence')
                            if key in graph.graph},
               'nodes': records,
               'edges': [{'source': indices[source], 'target': indices[target],
                          'attributes': {key: value(attrs[key]) for key in
                                         ('label', 'dist_relationship') if key in attrs}}
                         for source, target, attrs in graph.edges(data=True)]}
    with Path(path).open('x') as stream:
        json.dump(payload, stream, allow_nan=False, separators=(',', ':'))
        stream.write('\n')


def read(path):
    import networkx as nx
    payload = json.loads(Path(path).read_text())
    if payload.get('format') != FORMAT:
        raise ValueError('Unsupported native adapter graph format')
    value(payload)  # reject nonfinite values, including permissive JSON NaN
    graph = nx.MultiDiGraph() if payload['multigraph'] else nx.DiGraph()
    graph.graph.update(payload['metadata'])
    nodes = payload['nodes']
    for row in nodes:
        node = row['id']
        if not isinstance(node, (str, int)) or isinstance(node, bool) or node in graph:
            raise ValueError('Invalid or duplicate native node identity')
        graph.add_node(node, **row['attributes'])
    for row in payload['edges']:
        source, target = row['source'], row['target']
        if any(type(index) is not int or not 0 <= index < len(nodes) for index in (source, target)):
            raise ValueError('Invalid native edge endpoint')
        graph.add_edge(nodes[source]['id'], nodes[target]['id'], **row['attributes'])
    return graph
