"""The timer must publish both an empty and a populated work tree."""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

CHECKPOINT = Path(__file__).resolve().parents[1] / "scripts/checkpoint.sh"


class CheckpointTests(unittest.TestCase):
    def test_empty_then_populated_work_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            repo, remote = base / "repo", base / "remote.git"
            repo.mkdir()
            def git(*args):
                return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()
            subprocess.run(["git", "init", "-q", "-b", "worker/checkpoint", str(repo)], check=True)
            subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True)
            git("config", "user.name", "Worker Fixture")
            git("config", "user.email", "fixture@example.invalid")
            (repo / "scripts").mkdir()
            shutil.copy2(CHECKPOINT, repo / "scripts/checkpoint.sh")
            (repo / "batch.json").write_text(json.dumps({"return_branch": "worker/checkpoint"}))
            git("add", "batch.json", "scripts/checkpoint.sh")
            git("commit", "-qm", "baseline")
            git("remote", "add", "origin", str(remote))
            git("push", "-q", "origin", "worker/checkpoint")
            initial = git("rev-parse", "HEAD")
            subprocess.run([str(repo / "scripts/checkpoint.sh"), "empty"], cwd=repo, check=True, capture_output=True)
            self.assertEqual(git("rev-parse", "HEAD"), initial)
            (repo / "work").mkdir()
            (repo / "work/first.txt").write_text("progress\n")
            subprocess.run([str(repo / "scripts/checkpoint.sh"), "progress"], cwd=repo, check=True, capture_output=True)
            self.assertNotEqual(git("rev-parse", "HEAD"), initial)
            self.assertEqual(git("rev-parse", "HEAD"), git("ls-remote", "origin", "refs/heads/worker/checkpoint").split()[0])


if __name__ == "__main__":
    unittest.main()
