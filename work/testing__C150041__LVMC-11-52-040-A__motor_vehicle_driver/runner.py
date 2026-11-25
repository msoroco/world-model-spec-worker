"""External reviewed-packet Native parking entrypoint."""
import json
from pathlib import Path
import sys
from parking_runner import check_materialized_package, main
if __name__ == "__main__":
    if "--check" in sys.argv:
        if Path("reviewed-context.json").exists():
            raise ValueError("delivery draft embeds a review packet")
        check_materialized_package(Path.cwd(), json.loads(Path("scene.json").read_text()))
        print("external reviewed packet required for Native execution")
    else:
        sys.argv.extend(["--packet", "reviewed-context.json", "--source-root", ".", "--case", "park_parallel_lawful"])
        main()
