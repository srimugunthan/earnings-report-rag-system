"""behave hooks. Makes src/ and steps/ importable (as plain module names, not
a package), and resets per-scenario mutable state that would otherwise leak
between scenarios through the shared `context` object."""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "src"
STEPS_DIR = Path(__file__).resolve().parent / "steps"

# Must run at import time, not inside before_all: behave imports every file
# under steps/ (which do `import app`, `import ingest`, etc.) before it ever
# calls before_all, so setting sys.path there would be too late.
for _path in (SRC_DIR, STEPS_DIR):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))


def before_all(context):
    context.repo_root = REPO_ROOT


def before_scenario(context, scenario):
    # Ingestion scenarios accumulate chunk counts here across "I run the
    # ingestion" / "I run the ingestion again" within ONE scenario — reset
    # per scenario so an earlier scenario's runs can't leak in.
    context.run_summaries = []
