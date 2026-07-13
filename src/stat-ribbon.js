function requireArray(value, label) {
  if (!Array.isArray(value)) throw new TypeError(`${label} must be an array.`);
  return value;
}

export function statRibbonModel(site) {
  return [
    { value: requireArray(site?.entries, "entries").length, label: "ENTRIES" },
    { value: requireArray(site?.regions, "regions").length, label: "REGIONS" },
    { value: requireArray(site?.sources, "sources").length, label: "SOURCES" },
  ];
}

export function renderStatRibbon(container, site) {
  container.replaceChildren(...statRibbonModel(site).map(({ value, label }) => {
    const item = document.createElement("span");
    item.className = "stat";
    const number = document.createElement("strong");
    number.className = "stat-value";
    number.textContent = String(value);
    const name = document.createElement("span");
    name.className = "stat-label";
    name.textContent = label;
    item.append(number, name);
    return item;
  }));
  container.hidden = false;
}
