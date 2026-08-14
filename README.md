# PaperLens: Multimodal RAG over Scientific Papers (Text + Figures)

[![CI](https://github.com/yjkong04/multimodal-scientific-rag/actions/workflows/ci.yml/badge.svg)](https://github.com/yjkong04/multimodal-scientific-rag/actions/workflows/ci.yml)
[![repo](https://img.shields.io/badge/github-yjkong04%2Fmultimodal--scientific--rag-blue)](https://github.com/yjkong04/multimodal-scientific-rag)

**A multimodal retrieval-augmented generation system that answers questions over scientific papers by reasoning across both text and figures — grounding every claim in a cited passage or figure. Combines vision-language reasoning (Claude), hybrid dense retrieval over two modalities, multi-hop context assembly, and citation-level hallucination evaluation.**

**Keywords:** multimodal RAG · vision-language models · hybrid retrieval · pgvector · retrieval evaluation · hallucination benchmarking · FastAPI · Next.js

Ask *"What does Figure 3 show about the relationship between drug dose and tumor volume?"* and get a grounded, cited answer that pulls from the figure, its caption, and the surrounding methods and results — not a hallucination.

---

## The one-pager

### Problem
Text-only RAG is table stakes. But scientific knowledge lives as much in figures, plots, and diagrams as in prose — and the two are inseparable: a result in Figure 3 only makes sense next to the method in Section 2. Standard RAG throws the figures away and answers from text alone, so it either can't answer figure questions or makes something up. Answering them well means retrieving across *two modalities* and assembling context that spans both.

### User
- **Primary:** a researcher, grad student, or analyst doing a literature review who needs to interrogate a corpus of papers fast and trust the answer enough to cite it.
- **Corpus:** the [PubMed Central Open Access subset](https://www.ncbi.nlm.nih.gov/pmc/tools/openftlist/) — life-sciences papers with figures, clean licensing, real biomedical content.
- **Trust requirement:** every claim in an answer links back to a specific passage or figure. No citation, no claim.

### What "done" looks like (v1)
1. Ingest ~200 open-access papers: text chunked, figures extracted with captions, both embedded and stored.
2. A question hits **hybrid retrieval** over text chunks *and* figure records, and the top-k from both modalities are assembled into one context window.
3. A vision-language model (Claude) generates an answer that **cites specific figures and passages** and refuses when the corpus doesn't support an answer.
4. A **document viewer** frontend renders the source paper with the cited passages and figures highlighted.
5. A **hallucination benchmark**: a held-out question set with known answers, scored for groundedness, citation accuracy, and refusal-when-unsupported.

### Explicitly out of scope for v1
Multi-paper synthesis across the whole corpus, PDF layout parsing beyond what the tooling gives us, user accounts, and fine-tuning any model. Retrieval + grounded generation + citation is the whole job for v1.

### What I'd need to learn
- **Vision-language model integration** — passing figures (not just captions) to a VLM and getting grounded, structured output back.
- **Multi-vector / hybrid retrieval** — combining dense text embeddings with figure/caption embeddings and fusing the rankings sensibly.
- **Context assembly across modalities** — packing text + image context into a budget so the answer can span sections (multi-hop).
- **Retrieval + hallucination evaluation** — building a benchmark that actually measures grounding, not just "looks plausible."
- **pgvector at a real (small) scale** — indexing, distance operators, and query performance.

---

## Architecture (v1)

```
                 ┌──────────────────────────────────────────┐
   PMC OA  ──►   │  Ingestion:  text chunks + figures        │
   papers        │  (caption, image bytes) → embeddings      │
                 └───────────────┬──────────────────────────┘
                                 ▼
                        ┌─────────────────┐
                        │  pgvector store │  text_chunks · figures
                        └────────┬────────┘
                                 ▼
   question ─►  Hybrid retrieval (text k + figures k)  ─►  Context assembly
                                 │                              │
                                 ▼                              ▼
                        VLM (Claude) generates grounded, cited answer
                                 │
                                 ▼
                Next.js viewer: paper with highlighted citations
```

## Stack
- **Backend:** Python, FastAPI
- **Vector store:** Postgres + pgvector
- **VLM:** Claude (vision) for figure reasoning and answer generation; embeddings for retrieval
- **Frontend:** Next.js document viewer (later milestone)

## Status
Weeks 1–5 done: the API runs on a built-in demo store with zero setup, **and** on a real corpus — PubMed Central Open Access papers ingested into pgvector, answered by dense (HNSW cosine) retrieval, multi-hop context assembly, and a local vision-language model, with citations to real passages and figures. An evaluation harness scores retrieval, groundedness, and refusal, and drives a comparison across candidate local VLMs.

## Quickstart

```bash
# 1. Install deps
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Run the API (works with the built-in demo store, no DB required)
uvicorn api.main:app --reload

# 3. Try it
curl -s localhost:8000/health
curl -s -X POST localhost:8000/ask -H 'content-type: application/json' \
  -d '{"question": "What does the figure show about dose and response?"}' | python3 -m json.tool
```

### Run with Docker

A prebuilt image is published to GHCR:

```bash
docker run -p 8000:8000 ghcr.io/yjkong04/multimodal-scientific-rag:latest
curl -s localhost:8000/health
```

### Real corpus (pgvector)

```bash
# 1. Start Postgres + pgvector (schema auto-applied)
docker compose up -d db

# 2. Install the embedder (local Hugging Face sentence-transformers)
pip install -r requirements-ml.txt

# 3. Ingest real open-access papers into pgvector
python -m ingest --query "heart rate variability sepsis" --limit 5 --write

# 4. Serve /ask on the real corpus
PAPERLENS_STORE_BACKEND=pgvector uvicorn api.main:app --reload
curl -s -X POST localhost:8000/ask -H 'content-type: application/json' \
  -d '{"question": "How is heart rate variability used to predict sepsis?"}' | python3 -m json.tool
```

Embeddings default to `BAAI/bge-small-en-v1.5` (384-dim, CPU-friendly). For tests
or a torch-free run, set `PAPERLENS_EMBEDDER=hashing` (deterministic, not semantic).

## Evaluation

A held-out question set is scored on three axes, so the system is measured rather
than eyeballed:

- **Retrieval** — recall@k and MRR against gold source ids (which chunk/figure
  *should* ground the answer).
- **Groundedness** — inline-citation support rate (does the model cite what it was
  given?) plus citation-set precision/recall against the gold sources.
- **Refusal** — refusal precision/recall and answer accuracy on an unanswerable
  slice, so declining-when-unsupported is a measured behavior, not a hope.

```bash
# Runs on the demo corpus with no DB and no model (deterministic):
PAPERLENS_EMBEDDER=hashing python -m evaluation

# Real corpus + a corpus-specific eval set:
python -m evaluation --backend pgvector --dataset evaluation/datasets/pmc_eval.jsonl
```

### VLM comparison

The same harness scores each candidate generator on identical retrieval, so the
figure-reasoning models are compared apples-to-apples (`python -m evaluation
--sweep`). Retrieval is generator-independent; what differs is grounding and
refusal. The vision rows are filled by an offline GPU run — the baseline runs
anywhere:

| generator | citation P | citation R | groundedness | refusal recall | answer acc |
| --- | ---: | ---: | ---: | ---: | ---: |
| extractive (baseline) | ✓ runs | ✓ runs | n/a¹ | ✓ runs | ✓ runs |
| Qwen2.5-VL-3B-Instruct | — | — | — | — | — |
| Qwen2.5-VL-7B-Instruct | — | — | — | — | — |
| InternVL2.5-8B | — | — | — | — | — |
| Molmo-7B-D | — | — | — | — | — |
| SmolVLM-Instruct (baseline VLM) | — | — | — | — | — |

¹ The extractive baseline emits no inline citation markers, so groundedness is
undefined for it; it is judged by citation precision/recall instead. Adding a
candidate VLM is a one-line `GeneratorSpec` once its `Generator` subclass is
registered in `api/generation.py`.

## License
MIT
