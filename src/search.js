import { reviewState } from "./review-status.js";
import { normalizeQuery, SORT_MODES } from "./state.js";

export function normalizeSearchText(value) {
  return String(value ?? "").normalize("NFKC").toLocaleLowerCase("ko").trim().replace(/\s+/gu, " ");
}

/** Splits bare terms and quoted phrases; every returned term is required. */
export function parseSearchTerms(query) {
  const text = normalizeQuery(query);
  if ([...text].filter((character) => character === "\"").length % 2 !== 0) {
    return text.replaceAll("\"", " ").split(/\s+/u).map(normalizeSearchText).filter(Boolean);
  }
  const terms = [];
  const matcher = /"([^"\n]+)"|([^\s]+)/gu;
  for (const match of text.matchAll(matcher)) {
    const term = normalizeSearchText(match[1] ?? match[2]);
    if (term) terms.push(term);
  }
  return terms;
}

function scalarValues(value) {
  return Array.isArray(value) ? value : [value];
}

function sourceValues(entry) {
  if (!Array.isArray(entry.search_sources)) throw new TypeError(`Entry ${entry.id ?? "unknown"} has unresolved source references.`);
  return entry.search_sources.flatMap((source) => [
    source.id,
    source.raw,
    source.kind,
    source.verification_status,
    source.checked_at,
    ...source.urls,
  ]);
}

/** Builds the normalized searchable document specified by the v3 data contract. */
export function searchableDocument(entry) {
  const values = [
    entry.id, entry.name, entry.operator, entry.region_name, entry.address, entry.district, entry.category, entry.subtype, entry.subtype_note,
    entry.school_level, entry.year, entry.games, entry.notes, entry.public_note, entry.confidence, entry.operational_status,
    entry.resource_type, entry.scope, entry.theme_link, ...sourceValues(entry),
  ];
  return normalizeSearchText(values.flatMap(scalarValues).filter((value) => value != null).join(" "));
}

function matchesTerms(entry, terms) {
  if (terms.length === 0) return true;
  const document = searchableDocument(entry);
  return terms.every((term) => document.includes(term));
}

export function matchesQuery(entry, query) {
  return matchesTerms(entry, parseSearchTerms(query));
}

function entryValues(entry, field) {
  const fields = {
    region: "region_id",
    type: "resource_type",
    schoolLevel: "school_level",
    theme: "theme_link",
    status: "operational_status",
  };
  return scalarValues(entry[fields[field] ?? field]).map((value) => String(value));
}

function matchesGroup(entry, field, wanted) {
  if (wanted == null || wanted === "" || (Array.isArray(wanted) && wanted.length === 0)) return true;
  const selected = Array.isArray(wanted) ? wanted : [wanted];
  const values = new Set(entryValues(entry, field));
  return selected.some((value) => values.has(String(value)));
}

function compareText(left, right) {
  return String(left ?? "").localeCompare(String(right ?? ""), "ko");
}

function numericYear(value) {
  if (value == null || value === "") return null;
  const year = Number(value);
  return Number.isFinite(year) ? year : null;
}

function compareEntries(left, right, sort) {
  if (!sort) return left.index - right.index;
  if (sort === "name-asc" || sort === "name-desc") {
    const comparison = compareText(left.entry.name, right.entry.name);
    if (comparison !== 0) return sort === "name-asc" ? comparison : -comparison;
  } else if (sort === "year-asc" || sort === "year-desc") {
    const leftYear = numericYear(left.entry.year);
    const rightYear = numericYear(right.entry.year);
    const leftValid = leftYear !== null;
    const rightValid = rightYear !== null;
    if (leftValid && rightValid && leftYear !== rightYear) return sort === "year-asc" ? leftYear - rightYear : rightYear - leftYear;
    if (leftValid !== rightValid) return leftValid ? -1 : 1;
  }
  return compareText(left.entry.id, right.entry.id) || left.index - right.index;
}

/**
 * Applies textual AND matching and filter groups. Each non-empty group is ANDed;
 * selections within a group are ORed. A recognized sort mode is deterministic;
 * otherwise source order is retained.
 */
export function filterEntries(entries, state = {}) {
  const list = Array.isArray(entries) ? entries : [];
  const sort = SORT_MODES.includes(state.sort) ? state.sort : null;
  const terms = parseSearchTerms(state.query ?? "");
  return list
    .map((entry, index) => ({ entry, index }))
    .filter(({ entry }) => matchesTerms(entry, terms))
    .filter(({ entry }) => matchesGroup(entry, "region", state.region))
    .filter(({ entry }) => matchesGroup(entry, "type", state.type))
    .filter(({ entry }) => matchesGroup(entry, "category", state.category))
    .filter(({ entry }) => matchesGroup(entry, "schoolLevel", state.schoolLevel))
    .filter(({ entry }) => matchesGroup(entry, "theme", state.theme))
    .filter(({ entry }) => matchesGroup(entry, "scope", state.scope))
    .filter(({ entry }) => matchesGroup(entry, "status", state.status))
    .filter(({ entry }) => !state.reviewState?.length || state.reviewState.includes(reviewState(entry)))
    .sort((left, right) => compareEntries(left, right, sort))
    .map(({ entry }) => entry);
}
