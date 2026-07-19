import { createAppState, normalizeMulti, normalizeQuery, SORT_MODES, VIEW_MODES } from "./state.js";

export const URL_KEYS = Object.freeze(["view", "region", "type", "q", "category", "schoolLevel", "theme", "scope", "status", "sort", "entry"]);
const MULTI_KEYS = new Set(["category", "schoolLevel", "theme", "scope", "status"]);
const TYPE_VALUES = Object.freeze(["school", "event", "facility", "other"]);

function requireOptions(options) {
  if (!options || typeof options !== "object" || !options.allowed || typeof options.allowed !== "object" || !Array.isArray(options.entries)) {
    throw new TypeError("URL codec requires allowed values and an entry catalog.");
  }
  return options;
}

function isAllowed(value, options, key) {
  if (!value) return false;
  if (key === "entry" || key === "q") return true;
  const builtIn = key === "view" ? VIEW_MODES : key === "type" ? TYPE_VALUES : key === "sort" ? SORT_MODES : null;
  if (builtIn && !builtIn.includes(value)) return false;
  const allowed = options.allowed[key];
  return builtIn != null && allowed == null || Array.isArray(allowed) && allowed.map(String).includes(value);
}

function lastValid(values, options, key) {
  for (let index = values.length - 1; index >= 0; index -= 1) {
    const value = String(values[index]).normalize("NFKC").trim();
    if (isAllowed(value, options, key)) return value;
  }
  return null;
}

function orderedMulti(values, options, key) {
  const allowed = Array.isArray(options.allowed[key]) ? options.allowed[key].map(String) : [];
  const rank = new Map(allowed.map((value, index) => [value, index]));
  return normalizeMulti(values)
    .filter((value) => isAllowed(value, options, key))
    .sort((left, right) => rank.get(left) - rank.get(right));
}

function validEntryIds(entries) {
  return new Set(entries.map((entry) => String(typeof entry === "string" ? entry : entry.id)));
}

function isDefault(key, value) {
  if (key === "view") return value === "browse";
  return Array.isArray(value) ? value.length === 0 : value === (key === "q" ? "" : null);
}

/** Decodes a query string into a complete, serializable AppState. */
export function decodeUrl(search = "", options) {
  requireOptions(options);
  const params = new URLSearchParams(search.startsWith("?") ? search.slice(1) : search);
  const raw = {};
  for (const key of URL_KEYS) {
    const values = params.getAll(key);
    if (MULTI_KEYS.has(key)) {
      raw[key] = orderedMulti(values, options, key);
    } else if (key === "q") {
      raw.query = normalizeQuery(values.at(-1) ?? "");
    } else if (key === "entry") {
      const candidate = lastValid(values, options, key);
      const ids = validEntryIds(options.entries);
      raw.entry = candidate && ids.has(candidate) ? candidate : null;
    } else {
      raw[key] = lastValid(values, options, key);
    }
  }
  return createAppState(raw);
}

/** Encodes state in the one canonical key/value order. */
export function encodeUrl(state, options) {
  requireOptions(options);
  const normalized = createAppState(state);
  const pairs = [];
  for (const key of URL_KEYS) {
    const stateKey = key === "q" ? "query" : key;
    const value = normalized[stateKey];
    if (isDefault(key, value)) continue;
    if (MULTI_KEYS.has(key)) {
      for (const item of orderedMulti(value, options, key)) {
        pairs.push([key, item]);
      }
      continue;
    }
    if (key === "entry") {
      const ids = validEntryIds(options.entries);
      if (value && ids.has(value)) pairs.push([key, value]);
      continue;
    }
    if (isAllowed(value, options, key)) pairs.push([key, value]);
  }
  return pairs.length === 0
    ? ""
    : `?${pairs.map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(value)}`).join("&")}`;
}

/** Returns the canonical URL relative to the current pathname. */
export function canonicalUrl(locationLike, options) {
  const pathname = locationLike?.pathname ?? "";
  return `${pathname}${encodeUrl(decodeUrl(locationLike?.search ?? "", options), options)}${locationLike?.hash ?? ""}`;
}

export function isCanonicalUrl(locationLike, options) {
  const current = `${locationLike?.pathname ?? ""}${locationLike?.search ?? ""}${locationLike?.hash ?? ""}`;
  return current === canonicalUrl(locationLike, options);
}
