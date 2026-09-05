// Legacy regional display anchors are reference material, not independently supported cases.
// Preserve their IDs in the archival dataset; exclude the entire family from case aggregates.
export const isReferenceRecord = entry => String(entry.id ?? '').startsWith('visible-regional-');
export const caseEntries = entries => entries.filter(entry => !isReferenceRecord(entry));
export function caseSite(site) {
  const entries = caseEntries(site.entries);
  const ids = new Set(entries.map(entry => entry.id));
  const categories = new Map();
  for (const entry of entries) categories.set(entry.category, (categories.get(entry.category) ?? 0) + 1);
  return { ...site, entries, sources: site.sources.filter(source => ids.has(source.entry_id)),
    meta: { ...site.meta, entry_count: entries.length },
    archival_count: site.entries.length, reference_count: site.entries.length - entries.length,
    coverage_by_category: [...categories].map(([category, count]) => ({ category, count })),
  };
}
