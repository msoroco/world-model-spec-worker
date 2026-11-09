"""Live, tick-neutral scene-graph capture. Use the project's single environment."""
import json
import pickle
import time
from pathlib import Path

from carla_sgg.sgg import SGG, IgnoreWaypointPickler
from carla_sgg.sgg_abstractor import process_to_junction_rsv


class WaypointUnpickler(pickle.Unpickler):
    def persistent_load(self, identifier):
        if identifier == 'please_ignore_me':
            return None
        raise pickle.UnpicklingError('Unknown persistent ID: %r' % identifier)


def load_graph(path):
    """Load a trusted local graph; live Waypoint references become None."""
    with Path(path).open('rb') as stream:
        return WaypointUnpickler(stream).load()


def render_preview(graph, path):
    """Render every directed relation without crossings, plus presentation pages.

    Nodes repeat across rows to keep endpoints and labels unambiguous. Parallel
    labels remain separate lines (including duplicates); isolated nodes get rows.
    The saved graph is never modified.
    """
    import math
    import textwrap
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages
    from matplotlib.patches import FancyBboxPatch

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pairs = {}
    for source, target, attrs in graph.edges(data=True):
        pairs.setdefault((source, target), []).append(str(attrs.get('label', '(unlabelled)')))
    rows = [(source, target, sorted(labels)) for (source, target), labels in pairs.items()]
    rows.sort(key=lambda row: (str(row[0]) != 'ego', str(row[0]), str(row[1])))
    rows.extend((node, None, []) for node in sorted(graph, key=str) if graph.degree(node) == 0)

    def node_text(node):
        name = str(node)
        state = getattr(node, 'attr', {}).get('light_state')
        if state is not None:
            name += ' | ' + str(state)
        return '\n'.join(textwrap.wrap(name, width=29, break_long_words=True,
                                       break_on_hyphens=False))

    def row_height(row):
        source, target, labels = row
        lines = max(len(node_text(source).splitlines()),
                    len(node_text(target).splitlines()) if target is not None else 1,
                    sum(max(1, math.ceil(len(label) / 30)) for label in labels))
        return max(1.0, 0.28 * lines + 0.35)

    def draw_row(ax, row, y, height):
        source, target, labels = row
        state_colors = {'Red': '#f9d4d4', 'Yellow': '#fff0b3', 'Green': '#d2eddb'}
        def box(node, x):
            attrs = getattr(node, 'attr', {})
            color = state_colors.get(str(attrs.get('light_state')), '#e6edf5')
            if str(node) == 'ego':
                color = '#ffdfaf'
            elif str(node).startswith(('Road ', 'Lane ', 'Junction ')):
                color = '#eef1f4'
            ax.add_patch(FancyBboxPatch((x, y - height * 0.40), 4.15, height * 0.80,
                         boxstyle='round,pad=0.06', facecolor=color, edgecolor='#a8b6c5', linewidth=0.8))
            ax.text(x + 2.075, y, node_text(node), ha='center', va='center',
                    fontsize=11, color='#172b4d', linespacing=1.25)
        box(source, 0.15)
        if target is not None:
            box(target, 10.7)
            ax.annotate('', xy=(10.58, y), xytext=(4.42, y),
                        arrowprops=dict(arrowstyle='-|>', color='#52677d', lw=1.3))
            label = '\n'.join('\n'.join(textwrap.wrap(value, width=30)) for value in labels)
            ax.text(7.5, y, label, ha='center', va='center', fontsize=11,
                    color='#172b4d', linespacing=1.3,
                    bbox=dict(facecolor='white', edgecolor='none', pad=5))
        else:
            ax.text(7.5, y, 'isolated node', ha='center', va='center', color='#52677d')

    def draw_page(page_rows, title, size):
        fig, ax = plt.subplots(figsize=size)
        total = sum(row_height(row) for row in page_rows) or 1
        ax.set_xlim(0, 15)
        ax.set_ylim(-total, 0)
        ax.axis('off')
        fig.subplots_adjust(left=0.035, right=0.965, top=0.86, bottom=0.07)
        fig.text(0.045, 0.955, title, fontsize=19, weight='bold', color='#172b4d', va='top')
        fig.text(0.045, 0.91,
                 '%d nodes • %d directed relations | Source → relationship → target' %
                 (graph.number_of_nodes(), graph.number_of_edges()), fontsize=11, color='#52677d')
        fig.text(0.045, 0.025,
                 'Nodes repeat across rows. Stacked labels are parallel relations. Layout is schematic.',
                 fontsize=10, color='#52677d')
        y = 0
        for row in page_rows:
            height = row_height(row)
            draw_row(ax, row, y - height / 2, height)
            y -= height
        if not page_rows:
            ax.text(7.5, -0.5, 'Empty graph', ha='center')
        return fig

    scenario = path.parent.parent.name
    scenario = next((name for name in ('straight', 'intersection')
                     if scenario.startswith('sg-' + name + '-')), None)
    title = 'Scene graph · ' + ((scenario + ' · ') if scenario else '') + path.stem
    fig = draw_page(rows, title, (16, max(7, sum(row_height(r) for r in rows) * 0.72 + 2)))
    try:
        fig.savefig(str(path), dpi=160)
        with matplotlib.rc_context({'svg.fonttype': 'none'}):
            fig.savefig(str(path.with_suffix('.svg')))
    finally:
        plt.close(fig)

    # Bound each slide by its text height rather than dropping dense relations.
    pages, current, height = [], [], 0
    for row in rows:
        next_height = row_height(row)
        if current and height + next_height > 7:
            pages.append(current)
            current, height = [], 0
        current.append(row)
        height += next_height
    if current or not pages:
        pages.append(current)
    with PdfPages(str(path.with_suffix('.pdf'))) as pdf:
        for index, page_rows in enumerate(pages, 1):
            fig = draw_page(page_rows, '%s | %d / %d' % (title, index, len(pages)),
                            (16, max(9, sum(row_height(r) for r in page_rows) + 2)))
            try:
                pdf.savefig(fig)
                fig.savefig(str(path.with_name('%s-slide-%02d.png' % (path.stem, index))), dpi=160)
            finally:
                plt.close(fig)


class SceneGraphCollector:
    """Call capture immediately after your sole tick owner advances the world.

    Recreate for each new world/ego. Owns no actors, sensors, ticks or settings.
    SGG is an upstream singleton: use one collector per Python process.
    """
    def __init__(self, client, ego_id, output_dir, *, every=1, save_base=False, include_static_props=False, complete_driving_lanes=False):
        if every < 1:
            raise ValueError('every must be positive')
        self.world = client.get_world()
        if not self.world.get_settings().synchronous_mode:
            raise ValueError('Scene graph capture requires synchronous mode')
        if self.world.get_actor(ego_id) is None:
            raise ValueError('Ego actor does not exist')
        self.output = Path(output_dir)
        self.output.mkdir(parents=True, exist_ok=True)
        if (self.output / 'frames.jsonl').exists():
            raise FileExistsError('Use a new run directory; frames.jsonl already exists')
        self.include_static_props = include_static_props
        self.every, self.save_base = every, save_base
        self.calls, self.last_frame, self.saved = 0, None, 0
        started = time.perf_counter()
        self.generator = (SGG(client, ego_id, frame_buffer=1, complete_driving_lanes=True)
                          if complete_driving_lanes else SGG(client, ego_id, frame_buffer=1))
        self.initialization_seconds = time.perf_counter() - started
        (self.output / 'graphs/abstract').mkdir(parents=True, exist_ok=True)
        if save_base:
            (self.output / 'graphs/base').mkdir(parents=True, exist_ok=True)
        self.frames = (self.output / 'frames.jsonl').open('x', buffering=1)

    def capture(self, frame, ego_control=None, observed_evidence=None):
        snapshot = self.world.get_snapshot()
        if snapshot.frame != frame:
            raise RuntimeError('Requested frame is not the current world snapshot')
        if self.last_frame is not None and frame <= self.last_frame:
            raise ValueError('Frames must be strictly increasing')
        self.last_frame = frame
        selected = self.calls % self.every == 0
        self.calls += 1
        if not selected:
            return None
        started = time.perf_counter()
        base = self.generator.generate_graph_for_frame(frame, ego_control, include_static_props=self.include_static_props)
        base.graph["frame"] = frame
        base.graph["simulation_time_s"] = snapshot.timestamp.elapsed_seconds
        base.graph["units"] = {"position": "m", "carla_speed": "m/s"}
        if observed_evidence is not None:
            from original_observations import merge_graph
            merge_graph(base, observed_evidence)
        # The upstream crop retains full-world rendering caches by reference.
        # Save geometry only for retained nodes; original map/obstructions and
        # supplemental actors remain present. Do not mutate the generator cache.
        for key in ('bbox','node_colors','node_size'):
            if isinstance(base.graph.get(key),dict):
                base.graph[key]={node:value for node,value in base.graph[key].items() if node in base}
        abstract = (process_to_junction_rsv(base, include_static_props=True)
                    if self.include_static_props else process_to_junction_rsv(base))
        extraction_seconds = time.perf_counter() - started
        if self.world.get_snapshot().frame != frame:
            raise RuntimeError('World advanced during extraction; use a single tick owner')
        abstract_path = 'graphs/abstract/%08d.pkl' % frame
        with (self.output / abstract_path).open('xb') as stream:
            pickle.dump(abstract, stream, protocol=pickle.HIGHEST_PROTOCOL)
        base_path = None
        if self.save_base:
            base_path = 'graphs/base/%08d.pkl' % frame
            with (self.output / base_path).open('xb') as stream:
                IgnoreWaypointPickler(stream, protocol=pickle.HIGHEST_PROTOCOL).dump(base)
        record = dict(frame=frame, simulation_time=snapshot.timestamp.elapsed_seconds,
                      abstract=abstract_path, base=base_path,
                      nodes=abstract.number_of_nodes(), edges=abstract.number_of_edges(),
                      extraction_seconds=extraction_seconds,
                      capture_seconds=time.perf_counter() - started)
        self.frames.write(json.dumps(record) + '\n')
        self.saved += 1
        return record

    def close(self):
        self.frames.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
