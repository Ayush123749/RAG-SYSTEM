import json
from rag.config import TEXT_CHUNKS_PATH


class TextRetriever:
    def __init__(self):
        print("Loading text chunks...")
        self.chunks = []
        try:
            with open(TEXT_CHUNKS_PATH, 'r', encoding='utf-8') as f:
                for line in f:
                    try:
                        chunk = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if chunk.get("text"):
                        self.chunks.append(chunk)
        except MemoryError:
            print("Warning: Not enough memory to load all text chunks. Operating with empty text corpus.")
            self.chunks = []
        print(f"Loaded {len(self.chunks)} text chunks")

    def search(self, query, limit=10):
        query_lower = query.lower()
        query_words = set(query_lower.split())

        scored = []
        for chunk in self.chunks:
            text = chunk.get("text", "")
            if not text:
                continue
            text_lower = text.lower()
            score = 0
            if query_lower in text_lower:
                score += 5
            for word in query_words:
                if word in text_lower:
                    score += 1
            if score > 0:
                scored.append((score, chunk))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [chunk for _, chunk in scored[:limit]]

    def get_chunk_by_id(self, chunk_id):
        for chunk in self.chunks:
            if chunk.get("chunk_id") == chunk_id:
                return chunk
        return None

    def get_stats(self):
        total_chars = sum(len(chunk.get("text", "")) for chunk in self.chunks)
        return {
            "total_chunks": len(self.chunks),
            "total_chars": total_chars
        }
