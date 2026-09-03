"""Build the curated Rel-19 feature-summary layer.

Reads data_source/curated_features.json (human-maintained) and emits:

    data/_intermediate/curated_nodes.csv
    data/_intermediate/curated_edges.csv
    data/_intermediate/curated_chunks.jsonl

Curated nodes use the FEATURE_ prefix on entity_id so they cannot collide
with spec-extracted nodes. Edges use the standard relation_type vocabulary.
Each feature also produces a chunk for the text retriever, so user questions
about a feature can return a long-form paragraph even if the spec-extracted
entities are sparse.

Usage:
    python scripts/build_curated_layer.py
    python scripts/build_curated_layer.py --features data_source/curated_features.json
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FEATURES = REPO_ROOT / "data_source" / "curated_features.json"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "data" / "_intermediate"

NODE_COLUMNS = [
    "entity_id", "entity_type", "description", "chunk_ids", "source_files",
    "release", "created_at", "file_path", "source_id", "raw_entity_id",
]
EDGE_COLUMNS = [
    "source_id", "target_id", "relation_type", "weight", "description",
    "keywords", "source_id_edge", "file_path", "created_at", "source_file", "release",
]


def load_features(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def build_records(features: dict, created_at: int) -> dict:
    nodes: list[dict] = []
    edges: list[dict] = []
    chunks: list[dict] = []

    feat_index = {f["id"]: f for f in features.get("features", [])}

    for feat in features.get("features", []):
        fid = feat["id"]
        if not fid.startswith("FEATURE_"):
            print(f"  WARN: feature id {fid} does not start with FEATURE_; auto-prefixing")
            fid = "FEATURE_" + fid
            feat["id"] = fid
        chunk_id = f"curated-{fid}"
        chunk_text = feat.get("summary", "").strip()
        if not chunk_text:
            chunk_text = feat.get("description", "").strip()
        description = feat.get("description", "").strip() or chunk_text[:300]
        file_path = feat.get("source_file", "../3GPP-trunked/Rel-19-curated/TR_21.919")

        nodes.append({
            "entity_id": fid,
            "entity_type": feat.get("type", "Concept"),
            "description": description,
            "chunk_ids": chunk_id,
            "source_files": file_path,
            "release": "Rel-19",
            "created_at": str(created_at),
            "file_path": file_path,
            "source_id": chunk_id,
            "raw_entity_id": feat.get("name", fid.removeprefix("FEATURE_")),
        })

        if chunk_text:
            chunks.append({
                "chunk_id": chunk_id,
                "text": chunk_text,
                "source_file": file_path,
                "release": "Rel-19",
            })

        parent_id = feat.get("parent")
        if parent_id:
            edges.append({
                "source_id": parent_id,
                "target_id": fid,
                "relation_type": "has_subfeature",
                "weight": "1.0",
                "description": f"{parent_id} has the sub-feature {feat.get('name', fid)}",
                "keywords": "has_subfeature",
                "source_id_edge": chunk_id,
                "file_path": file_path,
                "created_at": str(created_at),
                "source_file": file_path,
                "release": "Rel-19",
            })

        for related in feat.get("related_specs", []):
            spec_node_id = related
            if not spec_node_id.startswith("TS ") and not spec_node_id.startswith("TR "):
                spec_node_id = "TS " + spec_node_id
            spec_node_id = spec_node_id.replace(" ", "_").replace("/", "_")
            edges.append({
                "source_id": fid,
                "target_id": spec_node_id,
                "relation_type": "specified_in",
                "weight": "1.0",
                "description": f"{feat.get('name', fid)} is specified in {related}",
                "keywords": "specified_in",
                "source_id_edge": chunk_id,
                "file_path": file_path,
                "created_at": str(created_at),
                "source_file": file_path,
                "release": "Rel-19",
            })

        for sub_id in feat.get("subfeatures", []):
            sub = feat_index.get(sub_id)
            if not sub:
                continue
            edges.append({
                "source_id": fid,
                "target_id": sub["id"],
                "relation_type": "has_subfeature",
                "weight": "1.0",
                "description": f"{feat.get('name', fid)} has sub-feature {sub.get('name', sub['id'])}",
                "keywords": "has_subfeature",
                "source_id_edge": chunk_id,
                "file_path": file_path,
                "created_at": str(created_at),
                "source_file": file_path,
                "release": "Rel-19",
            })

    for rel in features.get("relations", []):
        edges.append({
            "source_id": rel["source"],
            "target_id": rel["target"],
            "relation_type": rel.get("type", "related_to"),
            "weight": "1.0",
            "description": rel.get("description", ""),
            "keywords": rel.get("type", "related_to"),
            "source_id_edge": "curated-explicit-relation",
            "file_path": "../3GPP-trunked/Rel-19-curated/TR_21.919",
            "created_at": str(created_at),
            "source_file": "../3GPP-trunked/Rel-19-curated/TR_21.919",
            "release": "Rel-19",
        })

    return {"nodes": nodes, "edges": edges, "chunks": chunks}


def write_outputs(records: dict, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / "curated_nodes.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=NODE_COLUMNS)
        w.writeheader()
        for n in records["nodes"]:
            w.writerow({k: n.get(k, "") for k in NODE_COLUMNS})
    with (output_dir / "curated_edges.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=EDGE_COLUMNS)
        w.writeheader()
        for e in records["edges"]:
            w.writerow({k: e.get(k, "") for k in EDGE_COLUMNS})
    with (output_dir / "curated_chunks.jsonl").open("w", encoding="utf-8") as f:
        for c in records["chunks"]:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    print(f"  wrote {len(records['nodes'])} nodes, {len(records['edges'])} edges, "
          f"{len(records['chunks'])} chunks to {output_dir}")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--features", type=Path, default=DEFAULT_FEATURES)
    p.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = p.parse_args()

    if not args.features.exists():
        print(f"Features file not found: {args.features}")
        return 1

    print(f"Loading curated features from {args.features} ...")
    features = load_features(args.features)
    records = build_records(features, int(time.time()))
    print(f"Built {len(records['nodes'])} curated nodes, "
          f"{len(records['edges'])} edges, {len(records['chunks'])} chunks")
    write_outputs(records, args.output_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())