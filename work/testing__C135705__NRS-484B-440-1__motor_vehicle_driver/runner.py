"""C135705 Native entrypoint. --check is CPU only and never imports CARLA."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from native_construction import validate_scene


def check_scene(path):
    path=Path(path).resolve()
    scene=json.loads(path.read_text())
    source=(path.parent/scene["map_source"]).resolve()
    validate_scene(scene,source)
    if scene["source_kind"]!="worker engineering candidate; Native realization unverified":
        raise ValueError("candidate source provenance changed")
    return scene,source


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--scene",default="scene.json")
    parser.add_argument("--check",action="store_true")
    parser.add_argument("--output-dir")
    parser.add_argument("--host",default="127.0.0.1")
    parser.add_argument("--port",type=int,default=2000)
    args=parser.parse_args()
    scene,source=check_scene(args.scene)
    if args.check:
        print(json.dumps({"case_id":scene["case_id"],"static_construction_valid":True,
                          "native_started":False,"map_source_sha256":scene["map_source_sha256"]}))
    elif args.output_dir:
        from native_capture import run_native
        run_native(scene,args.output_dir,args.host,args.port,source,Path(args.scene).resolve())
    else:
        parser.error("use --check or --output-dir")


if __name__=="__main__":main()
