"""Synthetic negative proof that the C109749 comparator rejects a changed fixed actor path."""
import argparse
import json
import shutil
import sys
from pathlib import Path

FOLDER=Path(__file__).resolve().parent
sys.path.insert(0,str(FOLDER))
from comparison_audit import audit_pair


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--output-root',type=Path,required=True)
    p.add_argument('--left-source',type=Path,required=True)
    p.add_argument('--right-source',type=Path,required=True)
    a=p.parse_args();root=a.output_root.resolve()
    if root.exists():raise ValueError('Use a fresh comparison negative root')
    root.mkdir(parents=True)
    for name in ('config.json','intersection_geometry.json','video_frames.jsonl',
                 'interaction_history.jsonl','trace.jsonl'):
        shutil.copyfile(a.right_source/name,root/name)
    path=root/'interaction_history.jsonl'
    rows=[json.loads(s) for s in path.read_text().splitlines() if s]
    for vertex in rows[2]['ego']['body_vertices_xy_m']:
        vertex[0]+=3.0
    path.write_text(''.join(json.dumps(row,separators=(',',':'))+'\n' for row in rows))
    audit_pair(FOLDER,'reciprocal_response_after_turn',a.left_source,root,diagnostic_selftest=True)
    raise ValueError('Changed fixed actor trajectory was accepted')


if __name__=='__main__':main()
