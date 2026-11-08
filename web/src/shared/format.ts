export const pct = (x: number, digits = 0) => `${(x * 100).toFixed(digits)}%`;
export const signedPct = (x: number) => `${x >= 0 ? "+" : "−"}${Math.abs(x * 100).toFixed(1)} pts`;
export const euro = (x: number) => `€${x.toFixed(2)}`;
export const kappa = (k: number) => `κ ${k.toFixed(2)}`;

const LEVER_WORDS: Record<string, (v: unknown) => string> = {
  model: (v) => `${v} model`,
  retrieval_k: (v) => `retrieve ${v}`,
  jurisdiction_filter: (v) => (v ? "jurisdiction filter" : "no jurisdiction filter"),
  cite_only_retrieved: (v) => (v ? "cite only retrieved" : "may cite unretrieved"),
  answer_in_question_language: (v) => (v ? "answer in the question's language" : "language unconstrained"),
  quote_then_answer: (v) => (v ? "quote, then answer" : "answer directly"),
  self_check: (v) => (v ? "self-check" : "no self-check"),
  documents_as_data: (v) => (v ? "documents as data" : "documents not fenced"),
  injection_guard: (v) => (v ? "injection guard" : "no injection guard"),
  tone: (v) => `${v} tone`,
  verbosity: (v) => `${v}`,
  number_style: (v) => `numbers as ${v}`,
};

/** The levers a config changed from another, in words. */
export function changedLevers(from: Record<string, unknown>, to: Record<string, unknown>): string[] {
  return Object.keys(to)
    .filter((k) => from[k] !== to[k])
    .map((k) => (LEVER_WORDS[k] ?? ((v: unknown) => `${k} ${String(v)}`))(to[k]));
}
