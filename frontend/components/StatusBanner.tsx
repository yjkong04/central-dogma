import type { AskResponse } from "@/lib/types";
import styles from "./StatusBanner.module.css";

export function StatusBanner({
  response,
  error,
}: {
  response: AskResponse | null;
  error: string | null;
}) {
  if (error) {
    return <div role="alert" className={`${styles.banner} ${styles.error}`}>{error}</div>;
  }
  if (!response) return null;
  if (response.status === "refused") {
    return (
      <div role="status" className={`${styles.banner} ${styles.refused}`}>
        No supporting evidence in the corpus — I won&apos;t guess.
      </div>
    );
  }
  return (
    <div role="status" className={`${styles.banner} ${styles.answered}`}>
      backend: {response.backend} · confidence:{" "}
      {response.confidence != null ? response.confidence.toFixed(3) : "n/a"} · sections:{" "}
      {response.sections_covered}
    </div>
  );
}
