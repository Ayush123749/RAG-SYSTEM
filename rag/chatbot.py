from rag.config import TOP_K_GRAPH_RESULTS, TOP_K_TEXT_RESULTS, CHATBOT_MODEL, CHATBOT_TEMPERATURE, CHATBOT_MAX_TOKENS, OPENAI_API_KEY, OPENAI_BASE_URL, STOP_WORDS

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False


class RAGChatbot:
    def __init__(self, graph_store, text_retriever):
        self.graph = graph_store
        self.texts = text_retriever
        self.model = CHATBOT_MODEL
        self.temperature = CHATBOT_TEMPERATURE
        self.max_tokens = CHATBOT_MAX_TOKENS
        self.client = None
        if OPENAI_AVAILABLE and OPENAI_API_KEY:
            self.client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)

    def _two_pass_retrieve(self, query):
        query_lower = query.lower()
        query_words = set(query_lower.split())

        key_terms = query_words - STOP_WORDS

        first_pass = self.graph.search_by_text(query, limit=80)
        if not first_pass:
            return [], []

        scored = []
        for node in first_pass:
            score = 0
            entity_id = node.get('entity_id', '')
            text = self.graph.search_text.get(entity_id, '')

            if query_lower in text:
                score += 10

            for word in key_terms:
                if word in text:
                    score += 5

            neighbors = self.graph.get_neighbors(entity_id, limit=5)
            score += min(self.graph.neighbor_count.get(entity_id, 0), 10)

            entity_type = node.get('entity_type', '').lower()
            if any(word in entity_type for word in key_terms):
                score += 3

            scored.append((score, node, neighbors))

        scored.sort(key=lambda x: x[0], reverse=True)
        second_pass = [item[1] for item in scored[:10]]

        top_neighbors = {}
        for item in scored[:10]:
            node = item[1]
            neighbors = item[2]
            if neighbors:
                top_neighbors[node.get('entity_id')] = neighbors

        return second_pass, top_neighbors

    def _build_context(self, query):
        graph_results, top_neighbors = self._two_pass_retrieve(query)
        text_results = self.texts.search(query, limit=TOP_K_TEXT_RESULTS)

        context_parts = []
        context_parts.append("Top Graph Entities:")
        for node in graph_results[:10]:
            entity_id = node.get('entity_id', 'N/A')
            entity_type = node.get('entity_type', 'N/A')
            desc = node.get('description', '') or ''
            context_parts.append(f"- {entity_id} ({entity_type}): {desc[:300]}")
        context_parts.append("")

        if top_neighbors:
            context_parts.append("Connections:")
            for entity_id, neighbors in list(top_neighbors.items())[:5]:
                context_parts.append(f"- {entity_id} connections:")
                for n in neighbors[:5]:
                    context_parts.append(f"  {n['source']} -> [{n['relation']}] -> {n['target']}")
            context_parts.append("")

        context_parts.append("Relevant Text Chunks:")
        if text_results:
            for chunk in text_results[:5]:
                text = chunk.get("text", "")
                if text:
                    context_parts.append(text[:500])
                    context_parts.append("")
        else:
            context_parts.append("No relevant text chunks found.")

        return "\n".join(context_parts), graph_results, text_results

    def _generate_llm_response(self, query, context):
        if not self.client:
            return None

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an intelligent assistant for the 3GPP Rel-19 telecom knowledge graph. "
                                   "Analyze the provided knowledge graph context and answer the user's question intelligently. "
                                   "You may connect multiple entities and relationships from the context to form a coherent answer. "
                                   "Present the information naturally in plain text without any markdown, bullets, bold, or special formatting. "
                                   "Use complete sentences and paragraph form. "
                                   "If the context contains ANY related information, use it to construct the best possible answer. "
                                   "Only if the context is completely unrelated to the question should you respond with exactly: "
                                   "'this context is not available in the knowledge graph of rel19' and nothing else. "
                                   "Do not make up information beyond the provided context."
                    },
                    {
                        "role": "user",
                        "content": f"Question: {query}\n\nKnowledge Graph Context:\n{context}\n\nProvide a clear, intelligent answer in plain text based on the context above:"
                    }
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"LLM error: {e}")
            return None

    def _clean_llm_output(self, text):
        if not text:
            return text
        cleaned = text.strip()
        # Only treat it as a hard refusal if the whole response is effectively empty or exact refusal
        exact_refusal = "this context is not available in the knowledge graph of rel19"
        if cleaned.lower() == exact_refusal:
            return exact_refusal
        # Remove common preambles
        preambles = [
            "Based on the provided knowledge graph context, ",
            "Based on the context, ",
            "According to the knowledge graph context, ",
            "From the provided context, ",
            "The context indicates that ",
        ]
        for preamble in preambles:
            if cleaned.startswith(preamble):
                cleaned = cleaned[len(preamble):].strip()
                if cleaned and cleaned[0].islower():
                    cleaned = cleaned[0].upper() + cleaned[1:]
                break
        return cleaned

    def query(self, user_query):
        context, graph_results, text_results = self._build_context(user_query)

        # If no graph results found, return exact error message
        if not graph_results:
            return {
                "answer": "this context is not available in the knowledge graph of rel19",
                "graph_results": [],
                "text_results": text_results,
                "context": context
            }

        llm_answer = self._generate_llm_response(user_query, context)

        if llm_answer:
            answer = self._clean_llm_output(llm_answer)
        else:
            answer = "this context is not available in the knowledge graph of rel19"

        return {
            "answer": answer,
            "graph_results": graph_results,
            "text_results": text_results,
            "context": context
        }

    def get_stats(self):
        return {
            "graph": self.graph.get_stats(),
            "text": self.texts.get_stats()
        }
