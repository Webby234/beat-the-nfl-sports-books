"""PreToolUse hook: block hand edits to generated files.

reports/*.csv back the README's accuracy claims and must only change when a command regenerates them;
data/ is the downloaded nflverse cache. Scripts run through Bash are unaffected.
"""
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
try:
    path = json.load(sys.stdin).get("tool_input", {}).get("file_path", "")
    rel = (ROOT / path).resolve().relative_to(ROOT).as_posix()
except Exception:
    sys.exit(0)          # unreadable input or a file outside the project: not ours to guard
if (rel.startswith("reports/") and rel.endswith(".csv")) or rel.startswith("data/"):
    print(f"{rel} is generated. Regenerate it with the matching `python -m nfl_model ...` command "
          "(see /refresh-reports) instead of editing it by hand.", file=sys.stderr)
    sys.exit(2)
