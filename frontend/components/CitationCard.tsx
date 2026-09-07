import { useState } from "react";
import type { Citation } from "@/lib/types";
import styles from "./CitationCard.module.css";

export function CitationCard({
  citation,
  active,
  onActivate,
}: {
  citation: Citation;
  active: boolean;
  onActivate: (sourceId: string) => void;
}) {
  const [imgOk, setImgOk] = useState(true);
  const renderImage =
    citation.modality === "figure" &&
    !!citation.image_uri &&
    /^https?:\/\//.test(citation.image_uri) &&
    imgOk;
  return (
    <article
      className={styles.card}
      data-source-id={citation.source_id}
      data-active={active}
      onClick={() => onActivate(citation.source_id)}
    >
      <header className={styles.header}>
        <span>{citation.figure_label ?? citation.section ?? citation.paper_id}</span>
        <span className={styles.score}>{citation.score.toFixed(3)}</span>
      </header>
      {renderImage && (
        <img
          className={styles.image}
          src={citation.image_uri as string}
          alt={citation.figure_label ?? "figure"}
          onError={() => setImgOk(false)}
        />
      )}
      <p>{citation.snippet}</p>
    </article>
  );
}
