import { tokenizeAnswer } from "@/lib/citations";
import type { Citation } from "@/lib/types";
import styles from "./AnswerView.module.css";

export function AnswerView({
  answer,
  citations,
  activeSourceIds,
  onHoverSources,
}: {
  answer: string;
  citations: Citation[];
  activeSourceIds: string[];
  onHoverSources: (sourceIds: string[]) => void;
}) {
  const tokens = tokenizeAnswer(answer, citations);
  const hasMarkers = tokens.some((t) => t.kind === "marker");
  return (
    <div>
      <p className={styles.answer}>
        {tokens.map((t, i) =>
          t.kind === "text" ? (
            <span key={i}>{t.text}</span>
          ) : (
            <button
              key={i}
              type="button"
              className={styles.marker}
              data-marker={t.label}
              data-active={t.sourceIds.some((s) => activeSourceIds.includes(s))}
              onMouseEnter={() => onHoverSources(t.sourceIds)}
              onFocus={() => onHoverSources(t.sourceIds)}
              onClick={() => onHoverSources(t.sourceIds)}
            >
              {t.label}
            </button>
          )
        )}
      </p>
      {!hasMarkers && (
        <p className={styles.note}>
          Inline highlighting activates when the model cites its sources inline.
        </p>
      )}
    </div>
  );
}
