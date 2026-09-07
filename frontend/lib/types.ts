export type Modality = "text" | "figure";

export interface Citation {
  modality: Modality;
  paper_id: string;
  source_id: string;
  section: string | null;
  figure_label: string | null;
  image_uri: string | null;
  snippet: string;
  score: number;
}

export interface AskResponse {
  answer: string;
  citations: Citation[];
  status: "answered" | "refused";
  backend: string;
  confidence: number | null;
  sections_covered: number;
}

export interface AskRequest {
  question: string;
  top_k_text?: number;
  top_k_figures?: number;
}

export interface ApiError {
  error: string;
}
