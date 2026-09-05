export const RESOURCE_TYPES = Object.freeze(["school", "event", "facility", "other"]);
export const SORT_MODES = Object.freeze(["name-asc", "name-desc", "year-asc", "year-desc"]);
export const VIEW_MODES = Object.freeze(["browse", "compare"]);

const EMPTY_LIST = Object.freeze([]);
const DEFAULT_MAP_LOAD_STATE = Object.freeze({ status: "idle", region: null, error: null, generation: 0 });

export const DEFAULT_APP_STATE = Object.freeze({
  view: "browse",
  region: null,
  type: null,
  query: "",
  category: EMPTY_LIST,
  schoolLevel: EMPTY_LIST,
  theme: EMPTY_LIST,
  scope: EMPTY_LIST,
  status: EMPTY_LIST,
  reviewState: EMPTY_LIST,
  sort: null,
  entry: null,
  mapLoadState: DEFAULT_MAP_LOAD_STATE,
});

export const ActionTypes = Object.freeze({
  HYDRATE: "HYDRATE",
  SET_VIEW: "SET_VIEW",
  SET_REGION: "SET_REGION",
  SET_TYPE: "SET_TYPE",
  SET_QUERY: "SET_QUERY",
  SET_FILTER: "SET_FILTER",
  SET_SORT: "SET_SORT",
  SET_ENTRY: "SET_ENTRY",
  SET_MAP_LOAD_STATE: "SET_MAP_LOAD_STATE",
  RESET_FILTERS: "RESET_FILTERS",
});

const FILTER_FIELDS = new Set(["category", "schoolLevel", "theme", "scope", "status", "reviewState"]);
const MULTI_FIELDS = new Set(["category", "schoolLevel", "theme", "scope", "status", "reviewState"]);

export function normalizeQuery(value) {
  return String(value ?? "").normalize("NFKC").trim().replace(/\s+/gu, " ");
}

export function normalizeMulti(values) {
  const input = Array.isArray(values) ? values : values == null ? [] : [values];
  return [...new Set(input.map((value) => String(value).normalize("NFKC").trim()).filter(Boolean))]
    .sort((left, right) => left.localeCompare(right, "ko"));
}
function normalizeSort(value) {
  const sort = value == null ? "" : String(value).normalize("NFKC").trim();
  return SORT_MODES.includes(sort) ? sort : null;
}

function normalizeView(value) {
  const view = value == null ? "" : String(value).normalize("NFKC").trim();
  return VIEW_MODES.includes(view) ? view : "browse";
}


export function createAppState(overrides = {}) {
  const state = { ...DEFAULT_APP_STATE, ...overrides };
  const entry = state.entry == null || state.entry === "" ? null : String(state.entry);
  return {
    ...state,
    view: entry ? "browse" : normalizeView(state.view),
    entry,
    query: normalizeQuery(state.query),
    ...Object.fromEntries([...MULTI_FIELDS].map((field) => [field, normalizeMulti(state[field])])),
    sort: normalizeSort(state.sort),
    mapLoadState: normalizeMapLoadState(state.mapLoadState),
  };
}

function normalizeMapLoadState(value) {
  const state = value && typeof value === "object" ? value : {};
  const status = ["idle", "loading", "ready", "error"].includes(state.status) ? state.status : "idle";
  return {
    status,
    region: state.region == null ? null : String(state.region),
    error: state.error == null ? null : String(state.error),
    generation: Number.isSafeInteger(state.generation) && state.generation >= 0 ? state.generation : 0,
  };
}

export const actions = Object.freeze({
  hydrate: (state) => ({ type: ActionTypes.HYDRATE, state }),
  setView: (view) => ({ type: ActionTypes.SET_VIEW, view }),
  setRegion: (region) => ({ type: ActionTypes.SET_REGION, region }),
  setType: (resourceType) => ({ type: ActionTypes.SET_TYPE, resourceType }),
  setQuery: (query) => ({ type: ActionTypes.SET_QUERY, query }),
  setFilter: (field, values) => ({ type: ActionTypes.SET_FILTER, field, values }),
  setSort: (sort) => ({ type: ActionTypes.SET_SORT, sort }),
  setEntry: (entry) => ({ type: ActionTypes.SET_ENTRY, entry }),
  setMapLoadState: (mapLoadState) => ({ type: ActionTypes.SET_MAP_LOAD_STATE, mapLoadState }),
  resetFilters: () => ({ type: ActionTypes.RESET_FILTERS }),
});

export function appReducer(state = DEFAULT_APP_STATE, action = {}) {
  switch (action.type) {
    case ActionTypes.HYDRATE:
      return createAppState(action.state);
    case ActionTypes.SET_VIEW: {
      const view = normalizeView(action.view);
      return { ...state, view, entry: view === "compare" ? null : state.entry };
    }
    case ActionTypes.SET_REGION:
      return { ...state, region: action.region == null || action.region === "" ? null : String(action.region), entry: null };
    case ActionTypes.SET_TYPE:
      return { ...state, type: action.resourceType == null || action.resourceType === "" ? null : String(action.resourceType), entry: null };
    case ActionTypes.SET_QUERY:
      return { ...state, query: normalizeQuery(action.query) };
    case ActionTypes.SET_FILTER:
      if (!FILTER_FIELDS.has(action.field)) return state;
      return { ...state, [action.field]: normalizeMulti(action.values) };
    case ActionTypes.SET_SORT:
      return { ...state, sort: normalizeSort(action.sort) };
    case ActionTypes.SET_ENTRY:
      return {
        ...state,
        view: action.entry == null || action.entry === "" ? state.view : "browse",
        entry: action.entry == null || action.entry === "" ? null : String(action.entry),
      };
    case ActionTypes.SET_MAP_LOAD_STATE:
      return { ...state, mapLoadState: normalizeMapLoadState(action.mapLoadState) };
    case ActionTypes.RESET_FILTERS:
      return { ...state, region: null, type: null, query: "", category: [], schoolLevel: [], theme: [], scope: [], status: [], reviewState: [], sort: null, entry: null };
    default:
      return state;
  }
}

export const selectors = Object.freeze({
  activeFilterCount(state) {
    return [state.category, state.schoolLevel, state.theme, state.scope, state.status, state.reviewState]
      .reduce((count, values) => count + values.length, 0);
  },
  hasActiveFilters(state) {
    return Boolean(state.query) || selectors.activeFilterCount(state) > 0 || Boolean(state.sort);
  },
  selectedEntryId(state) {
    return state.entry;
  },
  isMapLoading(state) {
    return state.mapLoadState.status === "loading";
  },
});
