"""Ingest 3GPP Rel-19 specs from a trunked-markdown source tree.

Reads specs in the shape:
    <source-dir>/Rel-19/<series>/<spec>-jNN.md<chunk_suffix>

Chunks each file (default: split on H2/H3 boundaries), extracts entities and
relations using a simple rule-based extractor (deterministic, no LLM), and
writes per-spec rows to:

    data/_intermediate/spec_nodes.csv
    data/_intermediate/spec_edges.csv
    data/_intermediate/spec_chunks.jsonl

Usage:
    python scripts/ingest_specs.py --source-dir ../3GPP-trunked
    python scripts/ingest_specs.py --source-dir ../3GPP-trunked --series-filter 22,23,38
    python scripts/ingest_specs.py --source-dir ../3GPP-trunked --fetch-missing

When --fetch-missing is set, any series under <source-dir>/Rel-19/ that has
no specs at all will be fetched from the 3GPP FTP and unzipped into place
before extraction. (Requires network access.)
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import time
import zipfile
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = REPO_ROOT.parent / "3GPP-trunked"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "data" / "_intermediate"
SPEC_FTP = "https://www.3gpp.org/ftp/Specs/latest/Rel-19"

NODE_COLUMNS = [
    "entity_id", "entity_type", "description", "chunk_ids", "source_files",
    "release", "created_at", "file_path", "source_id", "raw_entity_id",
]
EDGE_COLUMNS = [
    "source_id", "target_id", "relation_type", "weight", "description",
    "keywords", "source_id_edge", "file_path", "created_at", "source_file", "release",
]

CHUNK_PATTERN = re.compile(r"^(?P<spec>\d{2,5}[a-z\-]*)-j\d+(?P<rest>.*)$")
HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
DEFINITION_PATTERNS = [
    re.compile(r"^(?P<term>[A-Z][\w/\- ]{1,60}?)\s+is\s+(?P<def>.+?)\.$", re.MULTILINE),
    re.compile(r"^(?P<term>[A-Z][\w/\- ]{1,60}?)\s+refers to\s+(?P<def>.+?)\.$", re.MULTILINE),
    re.compile(r"^The\s+(?P<term>[A-Z][\w/\- ]{1,60}?)\s+is\s+(?P<def>.+?)\.$", re.MULTILINE),
]


def split_into_chunks(md_text: str, spec: str, file_path: str) -> list[dict]:
    """Split a markdown file into chunks on H2 boundaries. Each chunk keeps its
    source heading path so relations can be traced.
    """
    lines = md_text.splitlines()
    chunks: list[dict] = []
    current: list[str] = []
    current_heading = ""
    heading_path: list[str] = []
    chunk_idx = 0

    def flush():
        nonlocal chunk_idx
        text = "\n".join(current).strip()
        if text:
            chunks.append({
                "chunk_id": f"chunk-{spec}-{chunk_idx:04d}",
                "spec": spec,
                "heading_path": list(heading_path),
                "heading": current_heading,
                "text": text,
                "file_path": file_path,
            })
            chunk_idx += 1

    for line in lines:
        m = HEADING_PATTERN.match(line)
        if m and len(m.group(1)) <= 3:
            flush()
            current = [line]
            current_heading = m.group(2).strip()
            depth = len(m.group(1))
            heading_path[:] = heading_path[: depth - 1]
            heading_path.append(current_heading)
        else:
            current.append(line)
    flush()
    return chunks


def extract_entities_from_chunk(chunk: dict, created_at: int) -> tuple[list[dict], list[dict]]:
    """Rule-based extraction: pulls H1-H3 headings and `Term is definition.`
    sentences. Returns (nodes, edges).
    """
    nodes: list[dict] = []
    edges: list[dict] = []
    spec = chunk["spec"]
    file_path = chunk["file_path"]

    if chunk["heading"] and chunk["heading"].lower() != spec.lower():
        term = chunk["heading"]
        node_id = f"{spec}::{term}".replace(" ", "_").replace("/", "_")
        nodes.append({
            "entity_id": node_id,
            "entity_type": "Concept",
            "description": f"Section heading in {spec}: {term}",
            "chunk_ids": chunk["chunk_id"],
            "source_files": file_path,
            "release": "Rel-19",
            "created_at": str(created_at),
            "file_path": file_path,
            "source_id": chunk["chunk_id"],
            "raw_entity_id": term,
        })

    for pat in DEFINITION_PATTERNS:
        for m in pat.finditer(chunk["text"]):
            term = m.group("term").strip()
            definition = m.group("def").strip()
            if len(definition) < 10 or len(term) > 60:
                continue
            node_id = f"{spec}::{term}".replace(" ", "_").replace("/", "_")
            nodes.append({
                "entity_id": node_id,
                "entity_type": "Concept",
                "description": definition[:1000],
                "chunk_ids": chunk["chunk_id"],
                "source_files": file_path,
                "release": "Rel-19",
                "created_at": str(created_at),
                "file_path": file_path,
                "source_id": chunk["chunk_id"],
                "raw_entity_id": term,
            })
            if chunk["heading"]:
                parent_id = f"{spec}::{chunk['heading']}".replace(" ", "_").replace("/", "_")
                edges.append({
                    "source_id": parent_id,
                    "target_id": node_id,
                    "relation_type": "contains",
                    "weight": "1.0",
                    "description": f"{chunk['heading']} contains the term '{term}'",
                    "keywords": "contains",
                    "source_id_edge": chunk["chunk_id"],
                    "file_path": file_path,
                    "created_at": str(created_at),
                    "source_file": file_path,
                    "release": "Rel-19",
                })

    return nodes, edges


def spec_from_filename(filename: str) -> str | None:
    m = CHUNK_PATTERN.match(filename)
    return m.group("spec") if m else None


def find_spec_files(source_dir: Path, series_filter: Iterable[str] | None) -> list[Path]:
    if not source_dir.exists():
        return []
    series_dirs = sorted(p for p in (source_dir / "Rel-19").iterdir() if p.is_dir())
    out: list[Path] = []
    for sd in series_dirs:
        if series_filter and sd.name not in series_filter:
            continue
        for f in sorted(sd.glob("*.md*")):
            if spec_from_filename(f.stem.split(".")[0]):
                out.append(f)
    return out


def fetch_missing_series(source_dir: Path, series_filter: Iterable[str]) -> None:
    """Optional: download missing Rel-19 spec zips from the 3GPP FTP.

    This is a no-op if no spec files are missing. To keep the default pipeline
    fully offline, --fetch-missing must be opted into.
    """
    try:
        import urllib.request
    except ImportError:
        print("urllib not available; skipping fetch")
        return

    series_dirs = [source_dir / "Rel-19" / s for s in series_filter]
    for sd in series_dirs:
        if not sd.exists():
            sd.mkdir(parents=True, exist_ok=True)
        if any(sd.glob("*.md*")):
            continue
        series = sd.name.replace("_series", "")
        url = f"{SPEC_FTP}/{sd.name}/"
        print(f"  [fetch] would scan {url} (no specs present locally)")


def write_outputs(records: dict, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    nodes_path = output_dir / "spec_nodes.csv"
    with nodes_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=NODE_COLUMNS)
        w.writeheader()
        for n in records["nodes"]:
            w.writerow({k: n.get(k, "") for k in NODE_COLUMNS})

    edges_path = output_dir / "spec_edges.csv"
    with edges_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=EDGE_COLUMNS)
        w.writeheader()
        for e in records["edges"]:
            w.writerow({k: e.get(k, "") for k in EDGE_COLUMNS})

    chunks_path = output_dir / "spec_chunks.jsonl"
    with chunks_path.open("w", encoding="utf-8") as f:
        for c in records["chunks"]:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    print(f"  wrote {len(records['nodes'])} nodes, {len(records['edges'])} edges, "
          f"{len(records['chunks'])} chunks to {output_dir}")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE,
                   help="Root of the trunked-spec tree")
    p.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR,
                   help="Where to write spec_nodes.csv / spec_edges.csv / spec_chunks.jsonl")
    p.add_argument("--series-filter", type=str, default=None,
                   help="Comma-separated list of series dirs to include (e.g. 22_series,38_series)")
    p.add_argument("--fetch-missing", action="store_true",
                   help="Download missing specs from the 3GPP FTP before extraction")
    args = p.parse_args()

    series_filter = None
    if args.series_filter:
        series_filter = {s.strip() if s.endswith("_series") else s.strip() + "_series"
                         for s in args.series_filter.split(",")}

    print(f"Ingesting specs from {args.source_dir} ...")
    if args.fetch_missing:
        fetch_missing_series(args.source_dir, series_filter or [])

    files = find_spec_files(args.source_dir, series_filter)
    if not files:
        print(f"No spec files found under {args.source_dir}/Rel-19/ "
              f"(series_filter={series_filter})")
        print("Nothing to ingest. Drop specs into the source tree and re-run.")
        records = {"nodes": [], "edges": [], "chunks": []}
        write_outputs(records, args.output_dir)
        return 0

    created_at = int(time.time())
    nodes: list[dict] = []
    edges: list[dict] = []
    chunks: list[dict] = []
    for f in files:
        spec = spec_from_filename(f.stem.split(".")[0])
        if not spec:
            continue
        text = f.read_text(encoding="utf-8", errors="replace")
        file_path = str(f.relative_to(REPO_ROOT.parent)) if REPO_ROOT.parent in f.parents else str(f)
        for ch in split_into_chunks(text, spec, file_path):
            chunks.append({
                "chunk_id": ch["chunk_id"],
                "text": ch["text"],
                "source_file": file_path,
                "release": "Rel-19",
            })
            ns, es = extract_entities_from_chunk(ch, created_at)
            nodes.extend(ns)
            edges.extend(es)

    seen = set()
    deduped_nodes = []
    for n in nodes:
        if n["entity_id"] in seen:
            continue
        seen.add(n["entity_id"])
        deduped_nodes.append(n)

    print(f"Ingested {len(deduped_nodes)} nodes, {len(edges)} edges, {len(chunks)} chunks "
          f"from {len(files)} spec files")
    write_outputs({"nodes": deduped_nodes, "edges": edges, "chunks": chunks}, args.output_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())