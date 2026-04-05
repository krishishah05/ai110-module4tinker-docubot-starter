# DocuBot

DocuBot is a lightweight retrieval-augmented documentation assistant that helps answer developer questions about a codebase. It demonstrates the difference between naive LLM generation, keyword-based retrieval, and full RAG (Retrieval-Augmented Generation).

It operates in three modes:

1. **Naive LLM mode** — Sends only the developer's question to Gemini. No docs are provided. The model answers from general training knowledge, which can produce fluent but unreliable responses.

2. **Retrieval only mode** — Uses a custom inverted index and IDF-weighted scoring system to retrieve relevant paragraph-level snippets from the docs. No LLM involved.

3. **RAG mode** — Retrieves the top-k snippets first, then passes them to Gemini with strict grounding instructions. The model is told to answer only from the provided snippets or say "I do not know."

---

## How Retrieval Works

The retrieval pipeline is implemented in `docubot.py`:

- **Inverted index** — On startup, every document is tokenized (lowercased, punctuation stripped) and mapped to a `{ word: [filenames] }` index for fast candidate lookup.
- **Paragraph-level splitting** — Documents are split on blank lines into individual paragraphs, so only the most relevant section is returned rather than an entire file.
- **IDF-weighted scoring** — Each query word is weighted by inverse document frequency: words that appear in fewer documents are more informative and score higher. Stop words are filtered out.
- **Prefix matching** — Query words are also matched against word prefixes in the text (e.g. `generated` matches `generate_access_token`), handling common stemming cases without external libraries.
- **Top-k selection** — Paragraphs are ranked by score and the top 5 are returned.

---

## Project Structure

```
module4-docubot/
├── docubot.py          # Core retrieval pipeline (index, scoring, retrieve, answer)
├── main.py             # CLI — runs all three modes interactively
├── llm_client.py       # Gemini API wrapper for naive and RAG generation
├── dataset.py          # Sample queries and fallback doc corpus
├── evaluation.py       # Retrieval hit-rate evaluation harness
├── model_card.md       # Observations comparing all three modes
├── requirements.txt
├── .env.example
└── docs/
    ├── API_REFERENCE.md
    ├── AUTH.md
    ├── DATABASE.md
    └── SETUP.md
```

---

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure your Gemini API key

```bash
cp .env.example .env
```

Edit `.env`:

```
GEMINI_API_KEY=your_api_key_here
```

Get a key at [aistudio.google.com/app/apikeys](https://aistudio.google.com/app/apikeys).  
Without a key, Retrieval Only mode (Mode 2) still works fully.

---

## Running DocuBot

```bash
python main.py
```

Choose a mode:

- **1** — Naive LLM (Gemini answers with no docs, from general knowledge)
- **2** — Retrieval only (no LLM, returns ranked paragraph snippets)
- **3** — RAG (retrieval + Gemini, grounded answers with citations)

Press Enter to run all built-in sample queries, or type a custom question.

---

## Running Retrieval Evaluation

```bash
python evaluation.py
```

Prints per-query hit/miss results and an overall hit rate against expected source files.

---

## Key Files

- **`docubot.py`** — Retrieval index, scoring, and snippet selection logic
- **`llm_client.py`** — Gemini prompt design and grounding instructions
- **`model_card.md`** — Completed observations comparing all three modes

---

## Requirements

- Python 3.9+
- Gemini API key (only needed for Modes 1 and 3)
- No database, no server, no external services beyond Gemini API calls
