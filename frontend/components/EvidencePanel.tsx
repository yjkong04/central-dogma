import type { Citation } from "@/lib/types";
import { CitationCard } from "./CitationCard";
import styles from "./EvidencePanel.module.css";

export function EvidencePanel({
  citations,
  activeSourceIds,
  onActivate,
}: {
  citations: Citation[];
  activeSourceIds: string[];
  onActivate: (sourceId: string) => void;
}) {
  if (citations.length === 0) return null;
  return (
    <aside aria-label="evidence" className={styles.panel}>
      <p className={styles.title}>Sources</p>
      {citations.map((c) => (
        <CitationCard
          key={c.source_id}
          citation={c}
          active={activeSourceIds.includes(c.source_id)}
          onActivate={onActivate}
        />
      ))}
    </aside>
  );
}
