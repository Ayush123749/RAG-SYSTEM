import networkx as nx
import csv
from collections import defaultdict

from rag.config import GRAPHML_PATH, NODES_CSV_PATH, EDGES_CSV_PATH, STOP_WORDS


class GraphStore:
    def __init__(self):
        print("Loading knowledge graph...")
        self.G = nx.read_graphml(GRAPHML_PATH)
        print(f"Graph loaded: {self.G.number_of_nodes()} nodes, {self.G.number_of_edges()} edges")

        self.nodes_index = {}
        self.type_index = defaultdict(list)
        self._build_indexes()

    def _build_indexes(self):
        print("Building indexes...")
        self.search_text = {}
        with open(NODES_CSV_PATH, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                entity_id = row['entity_id']
                self.nodes_index[entity_id] = row
                self.type_index[row['entity_type']].append(entity_id)
                self.search_text[entity_id] = (
                    f"{entity_id} {row.get('description', '')} {row.get('entity_type', '')}"
                ).lower()
        self.neighbor_count = {
            nid: self.G.degree(nid) for nid in self.nodes_index if nid in self.G
        }
        print(f"Indexed {len(self.nodes_index)} nodes")

    def get_node(self, entity_id):
        return self.nodes_index.get(entity_id)

    def get_neighbors(self, entity_id, direction="both", limit=50):
        if entity_id not in self.G:
            return []
        results = []
        if direction in ("both", "outgoing"):
            for _, target, data in self.G.edges(entity_id, data=True):
                results.append({
                    "source": entity_id,
                    "target": target,
                    "relation": data.get("keywords", "") or data.get("description", "RELATED_TO"),
                    "direction": "outgoing"
                })
        if direction in ("both", "incoming"):
            for source, _, data in self.G.in_edges(entity_id, data=True):
                results.append({
                    "source": source,
                    "target": entity_id,
                    "relation": data.get("keywords", "") or data.get("description", "RELATED_TO"),
                    "direction": "incoming"
                })
        return results[:limit]

    def search_by_type(self, entity_type, limit=20):
        ids = self.type_index.get(entity_type, [])
        return [self.nodes_index[nid] for nid in ids[:limit]]

    def search_by_text(self, query, limit=20):
        query_lower = query.lower()
        words = [w for w in query_lower.split() if w not in STOP_WORDS]
        scored = []
        for nid, text in self.search_text.items():
            score = 0
            if query_lower in text:
                score += 1
            for word in words:
                if word in text:
                    score += 1
            if score > 0:
                scored.append((score, self.nodes_index[nid]))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [node for _, node in scored[:limit]]

    def get_subgraph(self, entity_id, depth=1):
        nodes = {entity_id}
        edges = []
        current = {entity_id}
        for _ in range(depth):
            next_level = set()
            for nid in current:
                for _, target, data in self.G.edges(nid, data=True):
                    if target not in nodes:
                        next_level.add(target)
                        nodes.add(target)
                        edges.append({
                            "source": nid,
                            "target": target,
                            "relation": data.get("keywords", "") or data.get("description", "RELATED_TO")
                        })
                for source, _, data in self.G.in_edges(nid, data=True):
                    if source not in nodes:
                        next_level.add(source)
                        nodes.add(source)
                        edges.append({
                            "source": source,
                            "target": nid,
                            "relation": data.get("keywords", "") or data.get("description", "RELATED_TO")
                        })
            current = next_level
        return {
            "nodes": [self.nodes_index[nid] for nid in nodes if nid in self.nodes_index],
            "edges": edges
        }

    def get_stats(self):
        type_counts = {t: len(ids) for t, ids in self.type_index.items()}
        return {
            "total_nodes": self.G.number_of_nodes(),
            "total_edges": self.G.number_of_edges(),
            "entity_types": type_counts
        }
