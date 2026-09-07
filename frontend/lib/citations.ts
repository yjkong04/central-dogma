import type { Citation } from "./types";

// A token of the answer: literal prose, or a bracketed citation marker
// resolved to the source ids it points at.
export type AnswerToken =
  | { kind: "text"; text: string }
  | { kind: "marker"; label: string; sourceIds: string[] };

const MARKER = /\[([^\[\]]+)\]/g;

function norm(s: string | null): string {
  return (s ?? "").trim().toLowerCase();
}

// Figures match on figure_label; text passages match on section. Case-insensitive.
// A section can match multiple citations -> all their source ids are returned.
export function resolveMarker(label: string, citations: Citation[]): string[] {
  const key = norm(label);
  return citations
    .filter((c) =>
      c.modality === "figure" ? norm(c.figure_label) === key : norm(c.section) === key
    )
    .map((c) => c.source_id);
}

// Split an answer into ordered tokens. Unmatched markers degrade to literal text.
export function tokenizeAnswer(answer: string, citations: Citation[]): AnswerToken[] {
  const tokens: AnswerToken[] = [];
  let last = 0;
  for (const m of answer.matchAll(MARKER)) {
    const start = m.index ?? 0;
    if (start > last) tokens.push({ kind: "text", text: answer.slice(last, start) });
    const label = m[1];
    const sourceIds = resolveMarker(label, citations);
    if (sourceIds.length === 0) {
      tokens.push({ kind: "text", text: m[0] });
    } else {
      tokens.push({ kind: "marker", label, sourceIds });
    }
    last = start + m[0].length;
  }
  if (last < answer.length) tokens.push({ kind: "text", text: answer.slice(last) });
  return tokens;
}

export function hasInlineMarkers(answer: string, citations: Citation[]): boolean {
  return tokenizeAnswer(answer, citations).some((t) => t.kind === "marker");
}
