# DocuBot Model Card

This model card is a short reflection on your DocuBot system. Fill it out after you have implemented retrieval and experimented with all three modes:

1. Naive LLM over full docs  
2. Retrieval only  
3. RAG (retrieval plus LLM)

Use clear, honest descriptions. It is fine if your system is imperfect.

---

## 1. System Overview

**What is DocuBot trying to do?**  
DocuBot is a lightweight documentation assistant that helps developers find accurate answers to questions about a codebase by searching local project docs. It is designed to reduce hallucinations by grounding model responses in retrieved evidence rather than relying solely on a general-purpose LLM's training data. The goal is to provide trustworthy, citation-backed answers to questions like "Where is the auth token generated?" or "Which endpoint lists all users?"

**What inputs does DocuBot take?**  
A natural language developer question, plus a folder of documentation files (`.md` or `.txt`). Optionally, a `GEMINI_API_KEY` environment variable to enable LLM-powered modes.

**What outputs does DocuBot produce?**  
Depending on the mode: raw retrieved text snippets with source filenames (Retrieval Only), a generated natural language answer grounded in retrieved snippets (RAG), or a freely generated LLM response without retrieval grounding (Naive LLM). In all modes, when no relevant documentation is found, DocuBot returns "I do not know based on these docs."

---

## 2. Retrieval Design

**How does your retrieval system work?**  

- **Indexing:** On load, DocuBot reads all `.md` and `.txt` files and builds an inverted index. Each word (lowercased, punctuation stripped) maps to the list of filenames it appears in, enabling fast candidate lookup.
- **Scoring:** For a given query, candidate documents are found via the index. Each document is then split into paragraphs (separated by blank lines). Each paragraph is scored by counting how many query words appear in it, with a bonus for exact phrase matches.
- **Top snippet selection:** All scored paragraphs across all candidate files are sorted by score descending. The top-k (default: 3) paragraphs are returned as the retrieved snippets.

**What tradeoffs did you make?**  

- **Simplicity vs. semantic accuracy:** Word-count scoring requires no external libraries and is easy to reason about, but it cannot handle synonyms or paraphrased queries. A query phrased differently from the docs will get poor results even if relevant paragraphs exist.
- **Paragraph granularity:** Splitting by blank lines keeps snippets focused, but very long single-paragraph sections still return more text than necessary.
- **No stopword removal:** Common words slightly inflate scores, but removing them would require an extra dependency and is not necessary at this scale.

---

## 3. Use of the LLM (Gemini)

**When does DocuBot call the LLM and when does it not?**  

- **Naive LLM mode:** The LLM is called with only the developer's question and no documentation context. It answers from general training knowledge alone.
- **Retrieval only mode:** No LLM is used at all. Raw paragraph snippets are returned with their source filenames.
- **RAG mode:** Retrieval runs first. The top-k paragraphs are passed to the LLM alongside the question and strict grounding instructions.

**What instructions do you give the LLM to keep it grounded?**  
In RAG mode the prompt tells the model to: use only the provided snippets, not invent functions/endpoints/config values, reply with exactly "I do not know based on the docs I have." when snippets are insufficient, and cite which files it relied on when answering.

---

## 4. Experiments and Comparisons

| Query | Naive LLM: helpful or harmful? | Retrieval only: helpful or harmful? | RAG: helpful or harmful? | Notes |
|------|---------------------------------|--------------------------------------|---------------------------|-------|
| Where is the auth token generated? | Harmful — invents function names and file paths not in this project | Helpful — returns the correct AUTH.md paragraph citing `generate_access_token` | Helpful — accurate, cites AUTH.md, no invented details | Naive LLM sounds authoritative but fabricates |
| How do I connect to the database? | Partially helpful — generic SQLAlchemy advice that may not match this project | Helpful — returns the DATABASE.md paragraph showing `DATABASE_URL` examples | Helpful — synthesizes config info clearly, cites DATABASE.md | RAG is clearest here |
| Which endpoint lists all users? | Harmful — omits the admin-only 403 restriction entirely | Helpful — returns the correct API_REFERENCE.md snippet with the admin restriction | Helpful — correctly notes admin-only access, cites API_REFERENCE.md | Naive LLM's omission could cause a real security misunderstanding |
| How does a client refresh an access token? | Partially helpful — generic OAuth2 advice | Helpful — returns AUTH.md and API_REFERENCE.md paragraphs | Helpful — accurate step-by-step answer grounded in docs | All modes got the endpoint right; RAG gave the clearest explanation |
| Is there any mention of payment processing? | Harmful — invents a payment processing module with plausible-sounding endpoints | Helpful — returns "I do not know based on these docs." | Helpful — correctly refuses to answer | Best demonstration of why guardrails matter |
| Which fields are stored in the users table? | Partially helpful — guesses plausible fields that happen to match | Helpful — returns the exact DATABASE.md table schema | Helpful — lists exact fields, cites DATABASE.md | Retrieval and RAG both excellent here |

**What patterns did you notice?**  

- Naive LLM looks impressive but untrustworthy on generic-sounding questions where the docs have a specific implementation detail (e.g., exact function names, admin-only restrictions). The model produces fluent, confident answers that are partially or entirely fabricated.
- Retrieval only is clearly better when the docs contain the answer and the developer can interpret raw text. It is fully transparent — you can see exactly which file the answer came from.
- RAG is clearly better when the retrieved snippets contain the answer but need synthesis into readable prose. It combines the accuracy of retrieval with natural language generation, and the grounding instructions prevent model drift.
- RAG still fails when retrieval fails first: if the query is phrased very differently from the docs, wrong paragraphs are retrieved and the LLM generates a confident-sounding but incorrect answer from bad context.

---

## 5. Failure Cases and Guardrails

**Describe at least two concrete failure cases you observed.**  

> **Failure case 1:** Query: "Is there any mention of payment processing in these docs?"  
> Naive LLM responded with a detailed description of a payment processing module including endpoint names and config keys — none of which exist in the docs. The model hallucinated an entirely plausible-sounding feature. What should have happened: the system should refuse, since no relevant documentation exists.

> **Failure case 2:** Before paragraph-level splitting was added, Retrieval Only mode for "What environment variables are required for authentication?" returned the entire AUTH.md file. The specific variable names (`AUTH_SECRET_KEY`, `TOKEN_LIFETIME_SECONDS`) were buried inside a large wall of text. After refactoring to paragraph-level retrieval, only the relevant environment variables section was returned.

**When should DocuBot say "I do not know based on the docs I have"?**  

> - When no documents score above zero for the query, meaning none of the query words appear in any documentation file — the topic is simply not covered.
> - When the query asks about something clearly outside the project scope (e.g., payment processing, external services, infrastructure topics) and there are no matching paragraphs.

**What guardrails did you implement?**  

- **Empty retrieval refusal:** If `retrieve()` returns an empty list, both `answer_retrieval_only()` and `answer_rag()` immediately return "I do not know based on these docs." without calling the LLM.
- **LLM instruction-based refusal:** The RAG prompt explicitly tells the model to reply "I do not know based on the docs I have." if snippets are insufficient — a soft guardrail enforced via prompt design.
- **Score filtering:** Only paragraphs scoring above zero are included. Paragraphs with no query word matches are discarded, preventing irrelevant text from reaching the LLM.

---

## 6. Limitations and Future Improvements

**Current limitations**  

1. Keyword-only matching cannot handle semantic similarity — queries using synonyms or different phrasing from the docs get poor results even when highly relevant paragraphs exist.
2. All documents are treated equally. In a real system, authoritative files (e.g., the official API reference) should be weighted more heavily than informal notes.
3. Paragraph boundaries are fragile — splitting on blank lines works for well-formatted Markdown but poorly formatted docs or single-paragraph files return large, imprecise snippets.

**Future improvements**  

1. Add embedding-based semantic search (e.g., sentence transformers or the Gemini embeddings API) to find semantically similar paragraphs rather than just lexically matching ones.
2. Add a minimum score threshold so that very low-confidence matches trigger a refusal rather than passing barely relevant paragraphs to the LLM.
3. Include section header context in returned snippets so the LLM and the user can tell which part of a document a paragraph came from.

---

## 7. Responsible Use

**Where could this system cause real world harm if used carelessly?**  
In Naive LLM mode the model invents plausible-sounding API endpoints, environment variable names, and configuration values. A developer who trusts these outputs could introduce security vulnerabilities (e.g., using a weak `AUTH_SECRET_KEY` suggested by the model), waste time chasing non-existent code paths, or ship documentation errors. In RAG mode, if the docs themselves are outdated or incorrect, DocuBot will faithfully repeat those errors.

**What instructions would you give real developers who want to use DocuBot safely?**  

- Always verify DocuBot's answers against the actual source code or official documentation before acting on them, especially for security-sensitive configurations like authentication secrets and database credentials.
- Treat every answer as a starting point for investigation, not a final answer. Use the cited filenames to navigate directly to the relevant section.
- Keep the `docs/` folder up to date — DocuBot is only as accurate as the documentation it indexes.
- Do not use Naive LLM mode (Mode 1) for production decisions. It has no grounding and will fabricate details that sound plausible but may be entirely wrong for your specific codebase.
