// Presentation state is intentionally absent from the public URL contract.
export function initialPane(state) {
  return state.entry || state.region || state.type || state.query || state.sort
    || ["category", "schoolLevel", "theme", "scope", "status", "reviewState"].some(key => state[key]?.length)
    ? "list" : "map";
}
