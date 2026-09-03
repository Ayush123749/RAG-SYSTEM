from rag.graph_loader import GraphStore
from rag.text_retriever import TextRetriever
from rag.chatbot import RAGChatbot


def main():
    print("=" * 60)
    print("3GPP Rel-19 Telecom Knowledge Graph RAG Chatbot")
    print("=" * 60)

    graph = GraphStore()
    texts = TextRetriever()
    bot = RAGChatbot(graph, texts)

    print("\nSystem ready!")
    print(f"Graph: {graph.get_stats()['total_nodes']} nodes, {graph.get_stats()['total_edges']} edges")
    print(f"Text: {texts.get_stats()['total_chunks']} chunks")
    print("\nType 'quit' or 'exit' to stop.\n")

    while True:
        user_input = input("You: ").strip()
        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit"):
            break

        result = bot.query(user_input)
        print(f"\nBot: {result['answer']}\n")


if __name__ == "__main__":
    main()
