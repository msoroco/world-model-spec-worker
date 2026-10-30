"""Measure the predeclared physical settling trigger from original Native frames."""
import argparse
import hashlib
import json
from pathlib import Path

SAMPLES = 20
THRESHOLD_M = 0.05

def measure(rows, samples=SAMPLES):
    if len(rows) < samples:
        raise ValueError('Insufficient original subject body samples')
    selected = rows[:samples]
    frames = [row['original_frame'] for row in selected]
    times = [row['recording_time_s'] for row in selected]
    if any(b <= a for a, b in zip(frames, frames[1:])) or any(b <= a for a, b in zip(times, times[1:])):
        raise ValueError('Original frame or time sequence is not increasing')
    centroids = []
    for row in selected:
        vertices = row['ego']['body_vertices_m']
        if len(vertices) < 4 or any(len(point) < 3 for point in vertices):
            raise ValueError('Original subject body vertices are incomplete')
        centroids.append(sum(point[2] for point in vertices) / len(vertices))
    value = max(centroids) - min(centroids)
    return {'metric':'first_second_subject_vertical_centroid_range_m',
            'value_m':value,'threshold_m':THRESHOLD_M,'triggered':value > THRESHOLD_M,
            'frames':len(selected),'first_original_frame':frames[0],
            'last_original_frame':frames[-1]}

def main():
    p=argparse.ArgumentParser();p.add_argument('--evidence',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    rows=[json.loads(line) for line in args.evidence.read_text().splitlines() if line.strip()]
    result=measure(rows)
    result.update(format='worker-fallback-trigger-v1',source='capture/evidence.jsonl',
                  source_sha256=hashlib.sha256(args.evidence.read_bytes()).hexdigest(),
                  selection_policy='Use fallback1 only when this physical trigger is true; never select by legal outcome')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))
if __name__=='__main__':main()
