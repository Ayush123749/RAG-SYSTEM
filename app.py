from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
import os

# Load environment variables from .env file BEFORE importing config
load_dotenv()

from rag.config import GRAPHML_PATH, NODES_CSV_PATH, TEXT_CHUNKS_PATH, OPENAI_API_KEY, OPENAI_BASE_URL
from rag.graph_loader import GraphStore
from rag.text_retriever import TextRetriever
from rag.chatbot import RAGChatbot

app = Flask(__name__)
CORS(app)

# Set OpenAI API key if provided
if OPENAI_API_KEY:
    os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY

# Global instances - loaded once at startup
graph_store = None
text_retriever = None
chatbot = None

def load_models():
    global graph_store, text_retriever, chatbot
    if graph_store is None:
        graph_store = GraphStore()
        text_retriever = TextRetriever()
        chatbot = RAGChatbot(graph_store, text_retriever)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/health')
def health():
    return jsonify({"status": "ok"})

@app.route('/chat', methods=['POST'])
def chat():
    data = request.get_json()
    user_query = data.get('query', '').strip()
    
    if not user_query:
        return jsonify({"error": "Empty query"}), 400

    if chatbot is None:
        load_models()

    try:
        result = chatbot.query(user_query)
        return jsonify({
            "answer": result['answer'],
            "graph_results_count": len(result['graph_results']),
            "text_results_count": len(result['text_results'])
        })
    except Exception as e:
        app.logger.exception("Chat handler failed")
        return jsonify({"error": str(e)}), 500

@app.route('/stats')
def stats():
    if chatbot is None:
        load_models()
    return jsonify(chatbot.get_stats())

if __name__ == '__main__':
    print("Loading models...")
    load_models()
    print("Models loaded!")
    app.run(debug=True, host='0.0.0.0', port=5000)
