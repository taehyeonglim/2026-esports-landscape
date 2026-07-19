import { execFile } from "node:child_process";
import { mkdtemp, readFile, readdir, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { basename, join } from "node:path";
import { promisify } from "node:util";
import { fileURLToPath } from "node:url";

import { createProjection, geometryPath } from "../src/projection.js";

const run = promisify(execFile);
const root = fileURLToPath(new URL("..", import.meta.url));
const regionsDirectory = join(root, "geo/regions");
const outputPath = join(root, "data/national-map.v1.json");
const mapshaper = join(root, "node_modules/.bin/mapshaper");
const width = 720;
const height = 900;
const padding = 18;

const site = JSON.parse(await readFile(join(root, "data/site.v3.json"), "utf8"));
const regionById = new Map(site.regions.map((region) => [region.id, region]));
const regionFiles = (await readdir(regionsDirectory)).filter((name) => name.endsWith(".geojson")).sort();
if (regionFiles.length !== 17) throw new Error("National map generation requires exactly 17 region GeoJSON files.");

const features = [];
for (const file of regionFiles) {
  const regionId = basename(file, ".geojson");
  const region = regionById.get(regionId);
  if (!region) throw new Error(`Unknown region GeoJSON: ${regionId}`);
  const geojson = JSON.parse(await readFile(join(regionsDirectory, file), "utf8"));
  for (const feature of geojson.features) {
    features.push({
      ...feature,
      properties: { region_id: regionId, region_name: region.name },
    });
  }
}

const temporary = await mkdtemp(join(tmpdir(), "esports-national-map-"));
try {
  const combinedPath = join(temporary, "municipalities.geojson");
  const dissolvedPath = join(temporary, "regions.geojson");
  await writeFile(combinedPath, JSON.stringify({ type: "FeatureCollection", features }));
  await run(mapshaper, [
    combinedPath,
    "-dissolve", "region_id", "copy-fields=region_name",
    "-simplify", "weighted", "4%", "keep-shapes",
    "-o", "format=geojson", "precision=0.0001", dissolvedPath,
  ], { cwd: root });

  const dissolved = JSON.parse(await readFile(dissolvedPath, "utf8"));
  if (!Array.isArray(dissolved.features) || dissolved.features.length !== 17) {
    throw new Error("Dissolved national map must contain exactly 17 region features.");
  }
  const projection = createProjection(dissolved, { width, height, padding });
  const byId = new Map(dissolved.features.map((feature) => [feature.properties?.region_id, feature]));
  const regions = site.regions.map((region) => {
    const feature = byId.get(region.id);
    if (!feature) throw new Error(`Dissolved national map is missing ${region.id}.`);
    return { id: region.id, name: region.name, short_name: region.short_name, path: geometryPath(feature, projection) };
  });
  const payload = {
    schema_version: 1,
    view_box: `0 0 ${width} ${height}`,
    source: "KOSTAT 2018 municipality GeoJSON, dissolved and simplified for interactive reference use",
    regions,
  };
  await writeFile(outputPath, `${JSON.stringify(payload)}\n`);
  const bytes = Buffer.byteLength(JSON.stringify(payload));
  if (bytes > 150_000) throw new Error(`National map exceeds the 150KB runtime budget (${bytes} bytes).`);
  console.log(`Built ${regions.length}-region national map (${bytes} bytes).`);
} finally {
  await rm(temporary, { recursive: true, force: true });
}
