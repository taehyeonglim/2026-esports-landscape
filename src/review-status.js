export const REVIEW_LABELS = Object.freeze({confirmed:'근거 확인됨', due:'재검토 필요'});
export function reviewState(entry, asOf = new Date().toISOString().slice(0,10)) {
  const review = entry.operational_review;
  return entry.operational_status !== 'needs_review' && review?.next_review_at > asOf && review?.evidence_ids?.length ? 'confirmed' : 'due';
}
