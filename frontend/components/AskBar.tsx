import { useState } from "react";
import styles from "./AskBar.module.css";

export function AskBar({
  onAsk,
  disabled,
}: {
  onAsk: (question: string) => void;
  disabled: boolean;
}) {
  const [q, setQ] = useState("");
  const ready = q.trim().length >= 3;
  return (
    <form
      className={styles.bar}
      onSubmit={(e) => {
        e.preventDefault();
        if (ready) onAsk(q.trim());
      }}
    >
      <input
        className={styles.input}
        aria-label="question"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder="Ask a question over the corpus…"
      />
      <button className={styles.button} type="submit" disabled={disabled || !ready}>
        Ask
      </button>
    </form>
  );
}
