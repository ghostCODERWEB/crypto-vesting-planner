import json
import unittest
from cryptolab import *

EXAMPLE = json.loads(
    '{"timestamp": 150, "schedules": [{"id": "team", "total": 1000, "start": 100, "duration": 100, "cliff": 120, "claimed": 100}]}'
)


class EngineTests(unittest.TestCase):
    def test_boundaries(self):
        s = EXAMPLE["schedules"][0]
        self.assertEqual(vested(s, 119), 0)
        self.assertEqual(vested(s, 120), 200)
        self.assertEqual(vested(s, 200), 1000)

    def test_revocation(self):
        s = {**EXAMPLE["schedules"][0], "revoked_at": 140}
        self.assertEqual(vested(s, 999), 400)

    def test_claims(self):
        self.assertEqual(analyze(EXAMPLE)["claimable_total"], 400)

    def test_deterministic(self):
        self.assertEqual(analyze(EXAMPLE), analyze(EXAMPLE))

    def test_cli_json(self):
        import subprocess, sys

        result = subprocess.run(
            [sys.executable, "-m", "cryptolab", "examples/input.json"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), analyze(EXAMPLE))

    def test_cli_csv(self):
        import subprocess, sys, csv, io

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "cryptolab",
                "examples/input.json",
                "--format",
                "csv",
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            list(csv.reader(io.StringIO(result.stdout)))[0], ["path", "value"]
        )

    def test_duplicate_json_keys(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            path.write_text('{"a":1,"a":2}')
            with self.assertRaises(ValueError):
                load_input(path)

    def test_atomic_output(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "out.json"
            self.assertEqual(main(["examples/input.json", "--output", str(path)]), 0)
            self.assertEqual(json.loads(path.read_text()), analyze(EXAMPLE))

    def test_input_unchanged(self):
        import copy

        before = copy.deepcopy(EXAMPLE)
        analyze(EXAMPLE)
        self.assertEqual(before, EXAMPLE)


if __name__ == "__main__":
    unittest.main()
