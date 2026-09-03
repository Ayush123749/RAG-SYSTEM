import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DATA_DIR = os.path.join(BASE_DIR, "data")

GRAPHML_PATH = os.path.join(DATA_DIR, "rel19_3gpp_telecom_kg.graphml")
NODES_CSV_PATH = os.path.join(DATA_DIR, "nodes.csv")
EDGES_CSV_PATH = os.path.join(DATA_DIR, "edges.csv")
TEXT_CHUNKS_PATH = os.path.join(DATA_DIR, "rel19_text_chunks.jsonl")

CHATBOT_MODEL = "minimax/minimax-m3:free"
CHATBOT_TEMPERATURE = 0.7
CHATBOT_MAX_TOKENS = 1024

TOP_K_GRAPH_RESULTS = 80
TOP_K_SECOND_PASS = 10
TOP_K_TEXT_RESULTS = 5

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://openrouter.ai/api/v1")

STOP_WORDS = frozenset({
    "tell", "me", "about", "what", "is", "the", "a", "an", "of", "in", "for",
    "how", "does", "do", "can", "could", "would", "should", "may", "might",
    "will", "shall", "to", "and", "or", "but", "not", "no", "yes", "explain",
})
