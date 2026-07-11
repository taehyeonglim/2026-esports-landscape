import { regionGeoUrl, validateRegionGeoJson } from "./region-loader.js";
import { projectGeoJson } from "./projection.js";

function errorMessage(error) {
  return error instanceof Error ? error.message : String(error);
}

function fail(error) {
  return { ok: false, error: errorMessage(error) };
}

let handled = false;

self.addEventListener("message", async (event) => {
  if (handled) return;
  handled = true;
  const { baseUrl, origin, regionId, requestId } = event.data || {};
  const respond = (payload) => {
    self.postMessage({ ...payload, requestId });
    self.close();
  };
  let url;
  try {
    url = regionGeoUrl(baseUrl, regionId, origin);
  } catch (error) {
    respond(fail(new Error(`GeoJSON URL is invalid: ${errorMessage(error)}`)));
    return;
  }

  let response;
  try {
    response = await fetch(url, { headers: { Accept: "application/geo+json, application/json" } });
  } catch (error) {
    respond(fail(new Error(`GeoJSON request failed: ${errorMessage(error)}`)));
    return;
  }
  if (!response?.ok) {
    respond(fail(new Error(`GeoJSON request failed (${response?.status ?? "network"})`)));
    return;
  }

  let geojson;
  try {
    geojson = await response.json();
  } catch (error) {
    respond(fail(new Error(`GeoJSON response is not valid JSON: ${errorMessage(error)}`)));
    return;
  }
  try {
    validateRegionGeoJson(geojson);
  } catch (error) {
    respond(fail(new Error(`GeoJSON response failed validation: ${errorMessage(error)}`)));
    return;
  }

  try {
    const { path } = projectGeoJson(geojson);
    if (typeof path !== "string" || path.trim() === "") throw new Error("GeoJSON projection produced an empty path");
    respond({ ok: true, path });
  } catch (error) {
    respond(fail(new Error(`GeoJSON projection failed: ${errorMessage(error)}`)));
  }
});
