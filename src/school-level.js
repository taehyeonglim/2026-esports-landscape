// Normalize equivalent filter/grouping labels without rewriting source records.
// Mixed or audience labels (e.g. 중·고, 복합, 청소년) retain their own meaning.
const ALIASES = new Map([
  ["초등학교", "초"], ["중학교", "중"], ["고등학교", "고"],
  ["대학", "대"], ["대학교", "대"],
]);

export function normalizeSchoolLevel(value) {
  const text = String(value ?? "").normalize("NFKC").trim();
  return ALIASES.get(text) ?? text;
}
