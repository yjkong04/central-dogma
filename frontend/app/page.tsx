"use client";

import { useState } from "react";
import { ask } from "@/lib/api";
import type { AskResponse } from "@/lib/types";
import { AskBar } from "@/components/AskBar";
import { AnswerView } from "@/components/AnswerView";
import { EvidencePanel } from "@/components/EvidencePanel";
import { StatusBanner } from "@/components/StatusBanner";
import styles from "./page.module.css";

const EXAMPLES = [
  "What does the figure show about dose and response?",
  "How does the response change as the dose increases?",
];

export default function Page() {
  const [loading, setLoading] = useState(false);
  const [response, setResponse] = useState<AskResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeSourceIds, setActiveSourceIds] = useState<string[]>([]);

  async function run(question: string) {
    setLoading(true);
    setError(null);
    setResponse(null);
    setActiveSourceIds([]);
    try {
      setResponse(await ask({ question }));
    } catch (e) {
      setError(e instanceof Error ? e.message : "something went wrong");
    } finally {
      setLoading(false);
    }
  }

  function highlightFromMarker(ids: string[]) {
    setActiveSourceIds(ids);
    if (ids[0]) {
      document
        .querySelector(`[data-source-id="${ids[0]}"]`)
        ?.scrollIntoView?.({ block: "nearest", behavior: "smooth" });
    }
  }
  function highlightFromCard(sid: string) {
    setActiveSourceIds([sid]);
    document
      .querySelector(`[data-source-ids~="${sid}"]`)
      ?.scrollIntoView?.({ block: "nearest", behavior: "smooth" });
  }

  const showExamples = !response && !loading && !error;

  return (
    <main className={styles.main}>
      <h1>Central Dogma</h1>
      <AskBar onAsk={run} disabled={loading} />

      {showExamples && (
        <ul className={styles.examples}>
          {EXAMPLES.map((ex) => (
            <li key={ex}>
              <button type="button" className={styles.example} onClick={() => run(ex)}>
                {ex}
              </button>
            </li>
          ))}
        </ul>
      )}

      {loading && <p role="status">Searching the corpus…</p>}
      <StatusBanner response={response} error={error} />

      {response?.status === "answered" && (
        <div className={styles.split}>
          <AnswerView
            answer={response.answer}
            citations={response.citations}
            activeSourceIds={activeSourceIds}
            onHoverSources={highlightFromMarker}
          />
          <EvidencePanel
            citations={response.citations}
            activeSourceIds={activeSourceIds}
            onActivate={highlightFromCard}
          />
        </div>
      )}
    </main>
  );
}
