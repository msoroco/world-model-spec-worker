import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import native_headlamp_probe as probe


class NativeDispatchTests(unittest.TestCase):
    def test_executor_output_dir_dispatches_native_run_without_extra_flag(self):
        with tempfile.TemporaryDirectory() as directory:
            config = json.loads((Path(__file__).resolve().parents[1] / 'probe-config.json').read_text())
            source = Path(directory) / 'config.json'
            source.write_text(json.dumps(config))
            with patch.object(probe, 'run') as execute, patch.object(sys, 'argv', [
                    'native_headlamp_probe.py', '--config', str(source),
                    '--output-dir', str(Path(directory) / 'attempt'),
                    '--host', '127.0.0.1', '--port', '2000']):
                probe.main()
            execute.assert_called_once_with(config, str(Path(directory) / 'attempt'),
                                            '127.0.0.1', 2000)
            with patch.object(probe, 'run') as execute, patch.object(sys, 'argv', [
                    'native_headlamp_probe.py', '--config', str(source), '--check']):
                probe.main()
            execute.assert_not_called()


if __name__ == '__main__':
    unittest.main()
