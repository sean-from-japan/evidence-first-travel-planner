from __future__ import annotations

import json
import subprocess
import sys

from evidence_travel.cli import EXIT_FINDINGS, EXIT_INPUT, main
from tests.helpers import ROOT


def test_demo_writes_all_report_formats(tmp_path):
    output = tmp_path / "demo"
    assert main(["demo", "--output-dir", str(output)]) == EXIT_FINDINGS
    assert (output / "report.md").is_file()
    assert (output / "report.html").is_file()
    payload = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    assert payload["status"] == "invalid"
    assert payload["errors"] > 0


def test_cli_subprocess_has_stable_findings_exit_code(tmp_path):
    output = tmp_path / "report.md"
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "evidence_travel",
            "validate",
            str(ROOT / "examples" / "fictional_trip.json"),
            "--markdown",
            str(output),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == EXIT_FINDINGS
    assert json.loads(completed.stdout)["status"] == "invalid"


def test_cli_invalid_json_has_stable_input_exit_code(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{", encoding="utf-8")
    assert main(["validate", str(path)]) == EXIT_INPUT
