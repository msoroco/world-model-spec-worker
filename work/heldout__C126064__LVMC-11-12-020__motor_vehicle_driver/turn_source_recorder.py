"""Retain four original Native RGB streams and joined turn-body samples.

The caller owns the output directory and invokes close() even after failure.
No generated video belongs in the returned worker package.
"""
from hashlib import sha256
from pathlib import Path
import json
import subprocess
from threading import Lock


class SourceRecorder:
    def __init__(self, output, camera_sizes, fps=20):
        if fps != 20 or set(camera_sizes) != {
                'overview', 'approach', 'reference_corner', 'driver_reference'}:
            raise ValueError('Four named 20 Hz original cameras required')
        self.output = Path(output)
        self.output.mkdir(parents=True, exist_ok=True)
        self.sizes = camera_sizes
        self.lock = Lock()
        self.processes = {}
        self.frame_rows = {name: [] for name in camera_sizes}
        self.body_rows = []
        self.closed = False
        try:
            for name, (width, height) in camera_sizes.items():
                if type(width) is not int or type(height) is not int or min(width, height) < 1:
                    raise ValueError('Invalid original camera size')
                stderr = (self.output / f'{name}-encoder.log').open('wb')
                command = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
                           '-f', 'rawvideo', '-pixel_format', 'bgra',
                           '-video_size', f'{width}x{height}', '-framerate', '20',
                           '-i', 'pipe:0', '-an', '-c:v', 'ffv1', '-threads', '1',
                           str(self.output / f'{name}.mkv')]
                try:
                    process = subprocess.Popen(command, stdin=subprocess.PIPE,
                                               stdout=subprocess.DEVNULL, stderr=stderr)
                except BaseException:
                    stderr.close()
                    raise
                self.processes[name] = (process, stderr)
        except BaseException:
            self.close()
            raise

    def on_frame(self, name, image):
        with self.lock:
            if self.closed or name not in self.processes:
                raise ValueError('Original camera recorder closed or unknown')
            width, height = self.sizes[name]
            if (image.width, image.height) != (width, height):
                raise ValueError('Original camera size changed')
            payload = bytes(image.raw_data)
            if len(payload) != width * height * 4:
                raise ValueError('Incomplete original BGRA camera frame')
            rows = self.frame_rows[name]
            if rows and image.frame <= rows[-1]['native_frame']:
                raise ValueError('Original camera frames out of order')
            process = self.processes[name][0]
            if process.poll() is not None:
                raise ValueError('Original camera encoder exited early')
            process.stdin.write(payload)
            rows.append({'video_frame': len(rows), 'native_frame': int(image.frame),
                         'time_s': float(image.timestamp)})

    def record_sample(self, sample):
        with self.lock:
            if self.closed or not all(k in sample for k in
                                      ('frame', 'time_s', 'actor_id', 'corners_xy_m')):
                raise ValueError('Original turn body sample incomplete')
            if self.body_rows and sample['frame'] <= self.body_rows[-1]['frame']:
                raise ValueError('Original body frames out of order')
            self.body_rows.append(sample)

    def record_scene(self, case_id, authority_source, expected_sha256, markers, ego_actor_id):
        """Retain the exact authority claim and physical marker readback separately."""
        raw = Path(authority_source).read_bytes()
        if sha256(raw).hexdigest() != expected_sha256:
            raise ValueError('Marked intersection source hash changed')
        source = json.loads(raw)
        for field in ('municipal_jurisdiction_source', 'intersection_source',
                      'authorization_source', 'intersection_polygon_xy_m',
                      'indicated_course_xy_m'):
            if not source.get(field):
                raise ValueError('Marked intersection citation missing: ' + field)
        (self.output / 'authority_source_original.json').write_bytes(raw)
        scene = {'case_id': case_id, 'ego_actor_id': ego_actor_id,
                 'municipal_jurisdiction_source': source['municipal_jurisdiction_source'],
                 'intersection_source': source['intersection_source'],
                 'authorization_source': source['authorization_source'],
                 'median_opening_with_intersecting_road': source.get('median_opening_with_intersecting_road'),
                 'intersection_polygon_xy_m': source['intersection_polygon_xy_m'],
                 'indicated_course_xy_m': source['indicated_course_xy_m'],
                 'physical_markers_xy_m': markers['physical_marker_xy_m'],
                 'authority_source_sha256': expected_sha256,
                 'authorization_verified_by_worker': False}
        (self.output / 'marked_intersection.json').write_text(json.dumps(scene, indent=2) + '\n')
        return scene

    def record_indication_scene(self, case_id, authority_source, expected_sha256,
                                indications, ego_actor_id):
        """Retain a non-marker form without relabeling its readback as markers."""
        raw = Path(authority_source).read_bytes()
        if sha256(raw).hexdigest() != expected_sha256:
            raise ValueError('Indication intersection source hash changed')
        source = json.loads(raw)
        form = indications.get('indication_form')
        if form not in ('button', 'other_indication') or source.get('indication_form') != form:
            raise ValueError('Indication form differs from original source')
        for field in ('municipal_jurisdiction_source', 'intersection_source',
                      'authorization_source', 'intersection_polygon_xy_m',
                      'indicated_course_xy_m'):
            if not source.get(field):
                raise ValueError('Indication intersection citation missing: ' + field)
        if indications.get('source_sha256') != expected_sha256 or not indications.get('physical_xy_m'):
            raise ValueError('Physical indication readback missing or stale')
        (self.output / 'authority_source_original.json').write_bytes(raw)
        scene = {'case_id': case_id, 'ego_actor_id': ego_actor_id,
                 'municipal_jurisdiction_source': source['municipal_jurisdiction_source'],
                 'intersection_source': source['intersection_source'],
                 'authorization_source': source['authorization_source'],
                 'median_opening_with_intersecting_road': source.get('median_opening_with_intersecting_road'),
                 'intersection_polygon_xy_m': source['intersection_polygon_xy_m'],
                 'indicated_course_xy_m': source['indicated_course_xy_m'],
                 'indication_form': form,
                 'physical_indications_xy_m': indications['physical_xy_m'],
                 'authority_source_sha256': expected_sha256,
                 'authorization_verified_by_worker': False,
                 'visible_pixels_verified': False}
        (self.output / 'marked_intersection.json').write_text(json.dumps(scene, indent=2) + '\n')
        return scene

    def close(self):
        if self.closed:
            return
        self.closed = True
        failures = []
        for name, (process, stderr) in self.processes.items():
            try:
                if process.stdin and not process.stdin.closed:
                    process.stdin.close()
                if process.wait(timeout=30):
                    failures.append(name)
            finally:
                stderr.close()
        if failures:
            raise ValueError('Original camera encoder failed: ' + ', '.join(failures))

    def seal(self):
        self.close()
        frames = [row['frame'] for row in self.body_rows]
        if not frames or any([r['native_frame'] for r in rows] != frames
                             for rows in self.frame_rows.values()):
            raise ValueError('Four original camera streams do not join to body frames')
        if not (self.output / 'marked_intersection.json').is_file():
            raise ValueError('Original marked-intersection context missing')
        for rows in self.frame_rows.values():
            if any(abs(row['time_s'] - body['time_s']) > .05
                   for row, body in zip(rows, self.body_rows)):
                raise ValueError('Original camera/body timestamps differ')
        for name, rows in self.frame_rows.items():
            with (self.output / f'{name}-frames.jsonl').open('w') as stream:
                for row in rows:
                    stream.write(json.dumps(row) + '\n')
        with (self.output / 'turn_body.jsonl').open('w') as stream:
            for row in self.body_rows:
                stream.write(json.dumps(row) + '\n')
        with (self.output / 'trace.jsonl').open('w') as stream:
            for row in self.body_rows:
                corners = row['corners_xy_m']
                if len(corners) != 4:
                    raise ValueError('Original body trace needs four corners')
                centre = [sum(point[axis] for point in corners) / 4 for axis in (0, 1)]
                stream.write(json.dumps({'frame': row['frame'], 'time_s': row['time_s'],
                                         'position_m': centre}) + '\n')
        with (self.output / 'video_frames.jsonl').open('w') as stream:
            for index, body in enumerate(self.body_rows):
                stream.write(json.dumps({'video_frame': index,
                                         'carla_frame': body['frame'],
                                         'time_s': body['time_s']}) + '\n')
        return {'frames': len(frames), 'sources': sorted(self.frame_rows),
                'original_body_source': 'turn_body.jsonl',
                'original_trace_source': 'trace.jsonl',
                'frame_map_source': 'video_frames.jsonl',
                'scene_source': 'marked_intersection.json',
                'authority_source': 'authority_source_original.json',
                'authority_source_sha256': sha256(
                    (self.output / 'authority_source_original.json').read_bytes()).hexdigest()}
