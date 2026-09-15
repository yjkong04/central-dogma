"""Turn a question into a grounded, cited answer.

Hybrid retrieval over a candidate pool -> context assembly (dedupe, section
diversity for multi-hop coverage, budget) -> generation. Refusal is enforced in
three places, so the system never answers on nothing: empty retrieval, best
score below the relevance gate, or a generator that can't ground an answer.
"""

from __future__ import annotations

from .config import get_settings
from .context import assemble_context, sections_covered
from .generation import Generator
from .schemas import AskRequest, AskResponse, Citation
from .store import ScoredRecord, Store

_REFUSAL = (
    "I couldn't find anything in the corpus that supports an answer to that "
    "question, so I won't guess."
)


def _to_citation(scored: ScoredRecord) -> Citation:
    r = scored.record
    return Citation(
        modality=r.modality,
        paper_id=r.paper_id,
        source_id=r.source_id,
        section=r.section,
        figure_label=r.figure_label,
        image_uri=r.image_uri,
        snippet=r.text,
        score=round(scored.score, 4),
    )


def _refused(store: Store) -> AskResponse:
    return AskResponse(answer=_REFUSAL, citations=[], status="refused", backend=store.name)


def answer_question(req: AskRequest, store: Store, generator: Generator) -> AskResponse:
    settings = get_settings()
    mult = settings.retrieval_candidate_multiplier

    # Retrieve a larger pool than we'll keep, so the assembler has something to
    # diversify across sections (multi-hop coverage).
    paper_ids = [req.paper_id] if req.paper_id else None
    text_hits = store.search_text(req.question, req.top_k_text * mult, paper_ids)
    figure_hits = store.search_figures(req.question, req.top_k_figures * mult, paper_ids)
    candidates = [_to_citation(s) for s in (*text_hits, *figure_hits)]
    candidates.sort(key=lambda c: c.score, reverse=True)

    if not candidates:
        return _refused(store)

    # Relevance gate: don't answer on weak matches.
    best = candidates[0].score
    if best < settings.min_relevance_score:
        return _refused(store)

    context = assemble_context(
        candidates,
        char_budget=settings.context_char_budget,
        per_section_cap=settings.per_section_cap,
        max_figures=req.top_k_figures,
    )

    answer = generator.generate(req.question, context)
    if not answer.strip():
        return _refused(store)

    return AskResponse(
        answer=answer,
        citations=context,
        status="answered",
        backend=store.name,
        confidence=round(best, 4),
        sections_covered=sections_covered(context),
    )
