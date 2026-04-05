"""
Core DocuBot class responsible for:
- Loading documents from the docs/ folder
- Building a simple retrieval index (Phase 1)
- Retrieving relevant snippets (Phase 1)
- Supporting retrieval only answers
- Supporting RAG answers when paired with Gemini (Phase 2)
"""

import os
import glob
import re
import string


class DocuBot:
    def __init__(self, docs_folder="docs", llm_client=None):
        """
        docs_folder: directory containing project documentation files
        llm_client: optional Gemini client for LLM based answers
        """
        self.docs_folder = docs_folder
        self.llm_client = llm_client

        # Load documents into memory
        self.documents = self.load_documents()  # List of (filename, text)

        # Build a retrieval index (implemented in Phase 1)
        self.index = self.build_index(self.documents)

    # -----------------------------------------------------------
    # Document Loading
    # -----------------------------------------------------------

    def load_documents(self):
        """
        Loads all .md and .txt files inside docs_folder.
        Returns a list of tuples: (filename, text)
        """
        docs = []
        pattern = os.path.join(self.docs_folder, "*.*")
        for path in glob.glob(pattern):
            if path.endswith(".md") or path.endswith(".txt"):
                with open(path, "r", encoding="utf8") as f:
                    text = f.read()
                filename = os.path.basename(path)
                docs.append((filename, text))
        return docs

    # -----------------------------------------------------------
    # Index Construction (Phase 1)
    # -----------------------------------------------------------

    def build_index(self, documents):
        """
        Builds a tiny inverted index mapping lowercase words to the documents
        they appear in.

        Structure:
        {
            "token": ["AUTH.md", "API_REFERENCE.md"],
            "database": ["DATABASE.md"]
        }

        Splits on whitespace, lowercases tokens, strips punctuation.
        """
        index = {}
        for filename, text in documents:
            words = text.lower().split()
            for word in words:
                word = word.strip(string.punctuation)
                if not word:
                    continue
                if word not in index:
                    index[word] = []
                if filename not in index[word]:
                    index[word].append(filename)
        return index

    # -----------------------------------------------------------
    # Scoring and Retrieval (Phase 1)
    # -----------------------------------------------------------

    def score_document(self, query, text):
        """
        Returns a relevance score for how well the text matches the query.

        - Converts query into lowercase words (strips punctuation)
        - Counts how many query words appear in the text
        - Adds a bonus for exact phrase matches
        """
        query_lower = query.lower()
        text_lower = text.lower()

        words = query_lower.split()
        word_score = 0
        for word in words:
            word = word.strip(string.punctuation)
            if word and word in text_lower:
                word_score += text_lower.count(word)

        phrase_bonus = 5 if query_lower in text_lower else 0

        return word_score + phrase_bonus

    def _split_into_paragraphs(self, text):
        """
        Splits a document into paragraphs separated by blank lines.
        Filters out very short or empty paragraphs.
        """
        paragraphs = re.split(r'\n\s*\n', text)
        return [p.strip() for p in paragraphs if len(p.strip()) > 30]

    def retrieve(self, query, top_k=3):
        """
        Uses the index and scoring function to select top_k relevant document
        snippets. Returns a list of (filename, snippet_text) sorted by score
        descending.

        Retrieves at the paragraph level for precision: each document is split
        into paragraphs and the top-scoring paragraphs are returned.
        """
        if not self.documents:
            return []

        # Use the index to find candidate documents
        query_words = [w.strip(string.punctuation).lower() for w in query.split() if w.strip(string.punctuation)]
        candidate_files = set()
        for word in query_words:
            if word in self.index:
                candidate_files.update(self.index[word])

        # Fall back to all documents if index lookup found nothing
        if not candidate_files:
            candidates = self.documents
        else:
            candidates = [(fname, text) for fname, text in self.documents if fname in candidate_files]

        # Score at the paragraph level
        scored = []
        for filename, text in candidates:
            paragraphs = self._split_into_paragraphs(text)
            if not paragraphs:
                score = self.score_document(query, text)
                if score > 0:
                    scored.append((score, filename, text[:500]))
                continue
            for para in paragraphs:
                score = self.score_document(query, para)
                if score > 0:
                    scored.append((score, filename, para))

        # Sort by score descending and return top_k
        scored.sort(key=lambda x: x[0], reverse=True)

        results = []
        for score, filename, snippet in scored:
            results.append((filename, snippet))
            if len(results) >= top_k:
                break

        return results

    # -----------------------------------------------------------
    # Answering Modes
    # -----------------------------------------------------------

    def answer_retrieval_only(self, query, top_k=3):
        """
        Phase 1 retrieval only mode.
        Returns raw snippets and filenames with no LLM involved.
        """
        snippets = self.retrieve(query, top_k=top_k)

        if not snippets:
            return "I do not know based on these docs."

        formatted = []
        for filename, text in snippets:
            formatted.append(f"[{filename}]\n{text}\n")

        return "\n---\n".join(formatted)

    def answer_rag(self, query, top_k=3):
        """
        Phase 2 RAG mode.
        Uses student retrieval to select snippets, then asks Gemini
        to generate an answer using only those snippets.
        """
        if self.llm_client is None:
            raise RuntimeError(
                "RAG mode requires an LLM client. Provide a GeminiClient instance."
            )

        snippets = self.retrieve(query, top_k=top_k)

        if not snippets:
            return "I do not know based on these docs."

        return self.llm_client.answer_from_snippets(query, snippets)

    # -----------------------------------------------------------
    # Bonus Helper: concatenated docs for naive generation mode
    # -----------------------------------------------------------

    def full_corpus_text(self):
        """
        Returns all documents concatenated into a single string.
        This is used in Phase 0 for naive 'generation only' baselines.
        """
        return "\n\n".join(text for _, text in self.documents)
