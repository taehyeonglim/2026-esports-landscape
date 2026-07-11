export const PROJECTION_WIDTH = 860;
export const PROJECTION_HEIGHT = 680;
export const PROJECTION_PADDING = 26;

function validatePosition(position) {
  if (!Array.isArray(position) || position.length < 2 || !position.every(Number.isFinite)) throw new TypeError("Geometry coordinates must be finite positions");
}

function validateRing(ring) {
  if (!Array.isArray(ring) || ring.length < 4) throw new TypeError("Polygon rings must contain at least four positions");
  ring.forEach(validatePosition);
  const first = ring[0];
  const last = ring.at(-1);
  if (first[0] !== last[0] || first[1] !== last[1]) throw new TypeError("Polygon rings must be closed");
}

function validatePolygon(coordinates) {
  if (!Array.isArray(coordinates) || coordinates.length === 0) throw new TypeError("Polygon must contain rings");
  coordinates.forEach(validateRing);
}

function validateGeometry(geometry) {
  if (!geometry || typeof geometry !== "object") throw new TypeError("Geometry is required");
  if (geometry.type === "Feature") return validateGeometry(geometry.geometry);
  if (geometry.type === "FeatureCollection") {
    if (!Array.isArray(geometry.features) || geometry.features.length === 0) throw new TypeError("FeatureCollection must contain Features");
    geometry.features.forEach((feature) => {
      if (!feature || feature.type !== "Feature") throw new TypeError("FeatureCollection must contain Features");
      validateGeometry(feature.geometry);
    });
    return;
  }
  if (geometry.type === "Polygon") return validatePolygon(geometry.coordinates);
  if (geometry.type === "MultiPolygon") {
    if (!Array.isArray(geometry.coordinates) || geometry.coordinates.length === 0) throw new TypeError("MultiPolygon must contain polygons");
    geometry.coordinates.forEach(validatePolygon);
    return;
  }
  throw new TypeError("Geometry must be Polygon or MultiPolygon");
}

function positions(geometry) {
  if (geometry.type === "Feature") return positions(geometry.geometry);
  if (geometry.type === "FeatureCollection") return geometry.features.flatMap(positions);
  if (geometry.type === "Polygon") return geometry.coordinates.flat();
  return geometry.coordinates.flat(2);
}

export function geometryBounds(geometry) {
  validateGeometry(geometry);
  const coordinates = positions(geometry);
  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;
  for (const [x, y] of coordinates) {
    minX = Math.min(minX, x);
    minY = Math.min(minY, y);
    maxX = Math.max(maxX, x);
    maxY = Math.max(maxY, y);
  }
  return [minX, minY, maxX, maxY];
}

function projectionOptions(options) {
  if (options == null) options = {};
  if (typeof options !== "object" || Array.isArray(options)) throw new TypeError("Projection options must be an object");
  const { width = PROJECTION_WIDTH, height = PROJECTION_HEIGHT, padding = PROJECTION_PADDING } = options;
  if (![width, height, padding].every(Number.isFinite) || width <= 0 || height <= 0 || padding < 0) throw new TypeError("Projection dimensions and padding must be finite");
  return { width, height, padding };
}

export function createProjection(geometry, options) {
  const bounds = geometryBounds(geometry);
  const { width, height, padding } = projectionOptions(options);
  const [minX, minY, maxX, maxY] = bounds;
  const usableWidth = width - padding * 2;
  const usableHeight = height - padding * 2;
  if (!(usableWidth > 0 && usableHeight > 0)) throw new RangeError("Projection padding leaves no drawable area");
  const xRange = maxX - minX;
  const yRange = maxY - minY;
  if (!Number.isFinite(xRange) || !Number.isFinite(yRange)) throw new RangeError("Geometry bounds exceed the finite projection range");
  if (!(xRange > 0 && yRange > 0)) throw new RangeError("Geometry bounds must span both projection axes");
  const scale = Math.min(usableWidth / xRange, usableHeight / yRange);
  const offsetX = padding + (usableWidth - xRange * scale) / 2;
  const offsetY = padding + (usableHeight - yRange * scale) / 2;
  if (![scale, offsetX, offsetY].every(Number.isFinite) || scale <= 0) throw new RangeError("Projection arithmetic must remain finite");
  return Object.freeze({ bounds: Object.freeze(bounds), width, height, padding, scale, offsetX, offsetY, minX, minY, maxY });
}

function serialized(value) {
  return value.toFixed(1);
}

export function projectPosition(position, projection) {
  validatePosition(position);
  if (!projection || typeof projection !== "object" || ![projection.offsetX, projection.offsetY, projection.minX, projection.maxY, projection.scale].every(Number.isFinite) || projection.scale <= 0) {
    throw new TypeError("Valid projection is required");
  }
  const projected = [
    projection.offsetX + (position[0] - projection.minX) * projection.scale,
    projection.offsetY + (projection.maxY - position[1]) * projection.scale,
  ];
  if (!projected.every(Number.isFinite)) throw new RangeError("Projected position must remain finite");
  return projected;
}

function ringPath(ring, projection) {
  validateRing(ring);
  const points = ring.map((position) => {
    const [x, y] = projectPosition(position, projection);
    return `${serialized(x)},${serialized(y)}`;
  });
  const deduplicated = points.filter((point, index) => index === 0 || index === points.length - 1 || point !== points[index - 1]);
  return `${deduplicated.map((point, index) => `${index === 0 ? "M" : "L"}${point}`).join("")}Z`;
}

/** Creates an SVG path for validated Polygon, MultiPolygon, Feature, or FeatureCollection. */
export function geometryPath(geometry, projection = createProjection(geometry)) {
  validateGeometry(geometry);
  if (!projection) throw new TypeError("Valid projection is required");
  if (geometry.type === "Feature") return geometryPath(geometry.geometry, projection);
  if (geometry.type === "FeatureCollection") return geometry.features.map((feature) => geometryPath(feature, projection)).join("");
  if (geometry.type === "Polygon") return geometry.coordinates.map((ring) => ringPath(ring, projection)).join("");
  return geometry.coordinates.flatMap((polygon) => polygon.map((ring) => ringPath(ring, projection))).join("");
}

export function projectGeoJson(geometry, options) {
  const projection = createProjection(geometry, options);
  return { projection, path: geometryPath(geometry, projection) };
}
