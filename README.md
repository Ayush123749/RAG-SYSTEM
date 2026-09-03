# 3GPP Rel-19 Telecom Knowledge Graph RAG Chatbot

A Retrieval-Augmented Generation (RAG) chatbot built on top of the 3GPP Rel-19 telecom knowledge graph, using 2-pass filtering for improved retrieval accuracy and OpenRouter for LLM responses.

## Folder Structure

```
RAG SYSTEM/
├── data/
│   ├── rel19_3gpp_telecom_kg.graphml   # Complete knowledge graph (32 MB)
│   ├── nodes.csv                        # All graph nodes with attributes (7 MB)
│   ├── edges.csv                        # All graph edges with attributes (10 MB)
│   └── rel19_text_chunks.jsonl          # 896k text chunks for RAG context (207 MB)
├── rag/
│   ├── __init__.py
│   ├── config.py                        # Paths, model settings, and API config
│   ├── graph_loader.py                  # GraphML loading and graph queries
│   ├── text_retriever.py                # Text chunk loading and search
│   └── chatbot.py                       # RAG chatbot with 2-pass filtering + LLM
├── app.py                               # Flask web server
├── templates/
│   └── index.html                       # Chatbot frontend
├── requirements.txt
└── README.md
```

## Setup

1. Install dependencies:
   ```powershell
   pip install -r requirements.txt
   ```

2. Set your OpenRouter API key as an environment variable:
   ```powershell
   $env:OPENAI_API_KEY = "your-openrouter-key-here"
   ```

   Alternatively, you can hardcode it in `rag/config.py` by replacing the empty string in `OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")` with your key.

3. Run the web server:
   ```powershell
   python app.py
   ```

4. Open your browser and go to:
   ```
   http://localhost:5000
   ```

## LLM Configuration

The chatbot uses Groq AI as the LLM provider. Default settings:

- **Model**: `llama-3.1-8b-instant` (free tier available)
- **Base URL**: `https://api.groq.com/openai/v1`
- **Temperature**: 0.7
- **Max tokens**: 1024

You can change the model in `rag/config.py`:
```python
CHATBOT_MODEL = "llama-3.1-8b-instant"
```

Get your free API key from: https://console.groq.com/keys

## How It Works

### Graph Store (`graph_loader.py`)
- Loads the GraphML and CSV files into memory
- Builds indexes for fast node lookup by ID and entity type
- Provides graph search, neighbor lookup, and subgraph extraction

### Text Retriever (`text_retriever.py`)
- Loads the JSONL text chunks
- Performs keyword-based search over the text corpus

### RAG Chatbot (`chatbot.py`) - 2-Pass Filtering + LLM

The chatbot uses a **2-pass retrieval strategy** to improve context quality:

1. **First Pass (Broad Retrieval):**
   - Fetches up to **80 candidate entities** from the knowledge graph
   - Uses keyword matching against node IDs, descriptions, and entity types
   - No hard limit if fewer than 80 candidates exist

2. **Second Pass (Reranking):**
   - Takes the first pass results and reranks them using multiple signals:
     - **Exact phrase match**: +10 points
     - **Word overlap**: +2 points per matching word
     - **Node degree/connectivity**: + up to 10 points (highly connected nodes rank higher)
     - **Entity type match**: +3 points
   - Selects the **top 10** most relevant entities
   - No hard limit if fewer than 10 candidates exist

3. **Context Building:**
   - Adds descriptions for top 10 entities
   - Fetches and includes connections (neighbors) for top entities
   - Retrieves up to 5 relevant text chunks

4. **LLM Response Generation:**
   - Sends the retrieved context to OpenRouter API
   - Uses `poolside/laguna-s-2.1:free` model by default
   - If LLM is unavailable, falls back to returning raw context

## Example Queries

- "Tell me about UPF"
- "What is HTTP/2?"
- "Find all Technology entities"
- "Show me connections for SMF"
- "What is 5G authentication?"

## Graph Statistics

- **Total Nodes**: 21,540
- **Total Edges**: 31,718
- **Unique Edges after deduplication**: 23,472
- **Entity Types**: 30+ types including Concept, Terminology, Technology, Signal, Document, Application, etc.
- **Text Chunks**: 896,453 chunks from 3GPP Rel-19 specifications

## Notes

- All data is stored locally in the `data/` folder
- The knowledge graph is built from 3GPP Rel-19 specifications
- The text corpus file (`rel19_text_chunks.jsonl`) exists but currently contains empty text fields
- First-pass and second-pass limits are flexible - if fewer candidates exist, all are used
- LLM responses require an OpenRouter API key; without it, the bot returns raw graph context
