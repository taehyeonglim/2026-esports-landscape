const REGION_ID = /^[a-z0-9][a-z0-9-]*$/u;

function requireRegionId(regionId) {
  if (typeof regionId !== "string" || !REGION_ID.test(regionId)) throw new TypeError("Invalid region id");
  return regionId;
}

function requireBaseUrl(baseUrl) {
  if (typeof baseUrl !== "string" || baseUrl.length === 0 || baseUrl.startsWith("//")) {
    throw new TypeError("Base URL must be an absolute path or HTTP(S) URL");
  }
  if (/^https?:\/\//iu.test(baseUrl) || baseUrl.startsWith("/")) return baseUrl;
  throw new TypeError("Base URL must be an absolute path or HTTP(S) URL");
}

function httpUrl(value, label) {
  const url = new URL(value);
  if (url.protocol !== "http:" && url.protocol !== "https:") throw new TypeError(`${label} must use HTTP(S)`);
  return url;
}

export function regionGeoUrl(baseUrl, regionId, origin) {
  const region = requireRegionId(regionId);
  const base = requireBaseUrl(baseUrl);
  const relativePath = `geo/regions/${region}.geojson`;
  const absolute = /^https?:\/\//iu.test(base);
  if (origin == null) return absolute ? httpUrl(new URL(relativePath, base.endsWith("/") ? base : `${base}/`).href, "GeoJSON URL").href : `${base.endsWith("/") ? base : `${base}/`}${relativePath}`;
  if (typeof origin !== "string" || origin.length === 0) throw new TypeError("Origin must use HTTP(S)");
  const expectedOrigin = httpUrl(origin, "Origin");
  const url = absolute
    ? httpUrl(new URL(relativePath, base.endsWith("/") ? base : `${base}/`).href, "GeoJSON URL")
    : httpUrl(new URL(`${base.endsWith("/") ? base : `${base}/`}${relativePath}`, expectedOrigin).href, "GeoJSON URL");
  if (url.origin !== expectedOrigin.origin) throw new TypeError("GeoJSON URL must use the current origin");
  return url.href;
}

function errorMessage(error) {
  return error instanceof Error ? error.message : String(error);
}

function validatePosition(position) {
  if (!Array.isArray(position) || position.length < 2 || !position.every(Number.isFinite)) throw new TypeError("GeoJSON coordinates must be finite positions");
}

function validateRing(ring) {
  if (!Array.isArray(ring) || ring.length < 4) throw new TypeError("GeoJSON polygon rings must contain at least four positions");
  ring.forEach(validatePosition);
  const first = ring[0];
  const last = ring.at(-1);
  if (first[0] !== last[0] || first[1] !== last[1]) throw new TypeError("GeoJSON polygon rings must be closed");
}

function validatePolygon(coordinates) {
  if (!Array.isArray(coordinates) || coordinates.length === 0) throw new TypeError("GeoJSON Polygon must contain rings");
  coordinates.forEach(validateRing);
}

function validateGeometry(geometry) {
  if (!geometry || typeof geometry !== "object") throw new TypeError("GeoJSON geometry is required");
  if (geometry.type === "Polygon") return validatePolygon(geometry.coordinates);
  if (geometry.type === "MultiPolygon") {
    if (!Array.isArray(geometry.coordinates) || geometry.coordinates.length === 0) throw new TypeError("GeoJSON MultiPolygon must contain polygons");
    geometry.coordinates.forEach(validatePolygon);
    return;
  }
  throw new TypeError("GeoJSON geometry must be Polygon or MultiPolygon");
}

export function validateRegionGeoJson(geojson) {
  if (!geojson || typeof geojson !== "object" || geojson.type !== "FeatureCollection" || !Array.isArray(geojson.features) || geojson.features.length === 0) {
    throw new TypeError("GeoJSON response must be a non-empty FeatureCollection");
  }
  geojson.features.forEach((feature) => {
    if (!feature || typeof feature !== "object" || feature.type !== "Feature") throw new TypeError("GeoJSON FeatureCollection must contain Features");
    validateGeometry(feature.geometry);
  });
  return geojson;
}

/** Stale-safe, cache-backed GeoJSON loader. It has no dependency on rendering. */
export class RegionLoader {
  constructor({ baseUrl, fetchImpl, origin } = {}) {
    const fetcher = fetchImpl ?? globalThis.fetch?.bind(globalThis);
    if (typeof fetcher !== "function") throw new TypeError("fetchImpl is required");
    this.baseUrl = baseUrl;
    this.fetchImpl = fetcher;
    this.origin = origin;
    this.cache = new Map();
    this.controller = null;
    this.generation = 0;
    this.state = { status: "idle", region: null, error: null, generation: 0 };
  }

  getState() {
    return { ...this.state };
  }

  clear(regionId) {
    if (regionId == null) this.cache.clear();
    else this.cache.delete(requireRegionId(regionId));
  }

  abort() {
    this.generation += 1;
    this.controller?.abort();
    this.controller = null;
    if (this.state.status === "loading") {
      this.state = { status: "idle", region: this.state.region, error: null, generation: this.generation };
    }
  }

  async load(regionId) {
    const region = requireRegionId(regionId);
    const url = regionGeoUrl(this.baseUrl, region, this.origin);
    if (this.cache.has(region)) {
      this.abort();
      this.state = { status: "ready", region, error: null, generation: this.generation };
      return this.cache.get(region);
    }
    this.controller?.abort();
    const controller = new AbortController();
    const generation = ++this.generation;
    this.controller = controller;
    this.state = { status: "loading", region, error: null, generation };
    try {
      const response = await this.fetchImpl(url, { signal: controller.signal, headers: { Accept: "application/geo+json, application/json" } });
      if (!response?.ok) throw new Error(`GeoJSON request failed (${response?.status ?? "network"})`);
      const geojson = validateRegionGeoJson(await response.json());
      if (generation !== this.generation) return null;
      this.cache.set(region, geojson);
      this.state = { status: "ready", region, error: null, generation };
      return geojson;
    } catch (error) {
      if (generation !== this.generation) return null;
      if (error?.name === "AbortError") {
        this.state = { status: "idle", region, error: null, generation };
        return null;
      }
      this.state = { status: "error", region, error: errorMessage(error), generation };
      throw error;
    } finally {
      if (generation === this.generation) this.controller = null;
    }
  }
}
