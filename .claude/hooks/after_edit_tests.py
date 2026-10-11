"""PostToolUse hook: after Claude edits project code, run the tests that guard it.

features/ or data/ edited -> tests.test_no_leakage (~30s): nothing may use information from after kickoff.
ui/ edited               -> tests.test_ui (~1s).
Exit code 2 sends the failure back to Claude so it fixes it before moving on.
"""
import json, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RULES = (("nfl_model/features/", "tests.test_no_leakage"), ("nfl_model/data/", "tests.test_no_leakage"),
         ("nfl_model/ui/", "tests.test_ui"))

try:
    path = json.load(sys.stdin).get("tool_input", {}).get("file_path", "").replace("\\", "/")
except Exception:
    sys.exit(0)
mods = sorted({m for d, m in RULES if d in path and path.endswith(".py")})
for m in mods:
    r = subprocess.run([sys.executable, "-m", m], cwd=ROOT, capture_output=True, text=True)
    if r.returncode:
        tail = "\n".join((r.stdout + r.stderr).strip().splitlines()[-25:])
        print(f"{m} failed after editing {path}:\n{tail}", file=sys.stderr)
        sys.exit(2)
