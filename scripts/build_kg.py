"""End-to-end knowledge-graph rebuild.

Order:
    1. ingest_specs.py        (Tier 1: spec extraction; offline unless --fetch-missing)
    2. build_curated_layer.py  (Tier 2: curated Rel-19 feature summaries from TR 21.919)
    3. merge_and_export.py     (merge into data/nodes.csv, edges.csv, chunks.jsonl, graphml)

Usage:
    python scripts/build_kg.py
    python scripts/build_kg.py --fetch-missing
    python scripts/build_kg.py --skip-specs    # only run the curated layer + merge
    python scripts/build_kg.py --skip-curated  # only run the spec extraction + merge
    python scripts/build_kg.py --skip-merge    # run the extraction steps but don't write to data/
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
PY = sys.executable


def run(label: str, args: list[str]) -> None:
    print("=" * 70)
    print(f"  {label}")
    print("=" * 70)
    cmd = [PY, *args]
    res = subprocess.run(cmd, cwd=str(SCRIPTS_DIR.parent))
    if res.returncode != 0:
        sys.exit(res.returncode)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--fetch-missing", action="store_true",
                   help="Pass --fetch-missing through to ingest_specs.py")
    p.add_argument("--skip-specs", action="store_true",
                   help="Skip the spec extraction stage (curated layer only)")
    p.add_argument("--skip-curated", action="store_true",
                   help="Skip the curated layer stage (spec extraction only)")
    p.add_argument("--skip-merge", action="store_true",
                   help="Run the stages but skip the final merge/export")
    p.add_argument("--source-dir", type=str, default=None,
                   help="Override the spec source dir (forwarded to ingest_specs.py)")
    p.add_argument("--series-filter", type=str, default=None,
                   help="Comma-separated series list (forwarded to ingest_specs.py)")
    args = p.parse_args()

    if not args.skip_specs:
        ingest_args = [str(SCRIPTS_DIR / "ingest_specs.py")]
        if args.source_dir:
            ingest_args += ["--source-dir", args.source_dir]
        if args.series_filter:
            ingest_args += ["--series-filter", args.series_filter]
        if args.fetch_missing:
            ingest_args += ["--fetch-missing"]
        run("Stage 1: Spec extraction", ingest_args)

    if not args.skip_curated:
        run("Stage 2: Curated feature layer",
        [str(SCRIPTS_DIR / "build_curated_layer.py")])

    if not args.skip_merge:
        run("Stage 3: Merge and export",
        [str(SCRIPTS_DIR / "merge_and_export.py")])

    print("\nDone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())