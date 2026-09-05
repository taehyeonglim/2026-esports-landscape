import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';
import Ajv2020 from 'ajv/dist/2020.js';
import { readFileSync } from 'node:fs';

export const canonical = value => JSON.stringify(value, function (key, item) {
  return item && typeof item === 'object' && !Array.isArray(item)
    ? Object.fromEntries(Object.keys(item).sort().map(k => [k, item[k]])) : item;
});
export const digest = value => createHash('sha256').update(canonical(value)).digest('hex');
const schema = JSON.parse(readFileSync(new URL('../schemas/approved-reviews.v1.schema.json', import.meta.url)));
const validate = new Ajv2020({ allErrors: true }).compile(schema);
const note = status => ({current:'운영상태는 공개 자료를 바탕으로 현재로 기록되었습니다.',ended:'운영상태는 공개 자료를 바탕으로 종료로 기록되었습니다.',needs_review:'운영상태는 확인이 필요합니다. 이용 전 공개 자료를 확인해 주세요.'}[status]);
export function applyReviews(base, ledger) {
  if (!validate(ledger)) throw new Error(`Invalid approved reviews: ${JSON.stringify(validate.errors)}`);
  if (ledger.reviews.length) execFileSync('python3',['-m','esports_data.review_safety'],{input:JSON.stringify(ledger),env:{...process.env,PYTHONPATH:fileURLToPath(new URL('../src',import.meta.url))},stdio:['pipe','pipe','pipe']});
  const site = structuredClone(base);
  const ids = new Set();
  for (const review of ledger.reviews) {
    if (ids.has(review.id)) throw new Error('Duplicate review ID');
    ids.add(review.id);
    let entry = site.entries.find(e => e.id === review.entry_id);
    if (review.new_entry) {
      if (entry || review.prior_sha256 !== null || !review.evidence.length || !site.regions.some(r => r.id === review.new_entry.region_id) || !site.coverage_by_category.some(c => c.category === review.new_entry.category)) throw new Error('Invalid new admission');
      entry = {id:review.entry_id, ...review.new_entry, subtype:null,district:null,address:null,lat:null,lng:null,games:[],source:review.evidence.map(e=>e.url).join('; '),theme_link:null,confidence:null,subtype_note:null,notes:null,loc_approx:true,evidence_ids:[],coord_method:null,coord_note:null,source_ids:[],operational_status:'needs_review',public_note:note('needs_review'),status_provenance:null,status_checked_at:null,review:{status:'needs_review',reason:review.reason},off_map:true};
      site.entries.push(entry);
    }
    if (!entry || (!review.new_entry && digest(entry) !== review.prior_sha256)) throw new Error(`Review precondition conflict: ${review.entry_id}`);
    for (const day of [review.checked_at, review.approved_at, review.next_review_at]) {
      if (new Date(day).toISOString().slice(0,10) !== day) throw new Error('Invalid review date');
    }
    if (review.checked_at > review.approved_at || review.next_review_at <= review.checked_at) throw new Error('Invalid review chronology');
    const status = review.changes.operational_status ?? entry.operational_status;
    if (status !== 'needs_review' && (!review.evidence.length || !review.status_supported)) throw new Error('Status requires official evidence attestation');
    if (Object.keys(review.changes).some(k => k !== 'operational_status') && !review.evidence.length) throw new Error('Corrections require official evidence');
    Object.assign(entry, review.changes);
    entry.public_note = note(status);
    entry.status_checked_at = status === 'needs_review' ? null : review.checked_at;
    entry.status_provenance = status === 'needs_review' ? null : review.id;
    entry.review = {status: status === 'needs_review' ? 'needs_review' : 'reviewed', reason: review.reason};
    entry.operational_review = {id: review.id, checked_at: review.checked_at, next_review_at: review.next_review_at, reason: review.reason, evidence_ids: []};
    entry.off_map = !(entry.scope === 'regional' && Number.isFinite(entry.lat) && Number.isFinite(entry.lng));
    for (const [index, evidence] of review.evidence.entries()) {
      const url = new URL(evidence.url);
      if (url.protocol !== 'https:' || url.username || url.password) throw new Error('Unsafe evidence URL');
      const id = `${review.id}-e${index}`;
      if (site.sources.some(s => s.id === id)) throw new Error('Duplicate evidence ID');
      site.sources.push({id, entry_id:entry.id, raw:evidence.summary, urls:[evidence.url], kind:'raw_source', verification_status:'verified', checked_at:review.checked_at, evidence_sha256:evidence.sha256, publisher_id:evidence.publisher_id});
      entry.source_ids.push(id);
      entry.operational_review.evidence_ids.push(id);
    }
    site.meta.data_updated_at = [site.meta.data_updated_at, review.approved_at].sort().at(-1);
    site.meta.last_reviewed_at = [site.meta.last_reviewed_at ?? '', review.checked_at].sort().at(-1);
    if (status !== 'needs_review') site.meta.validation_as_of = [site.meta.validation_as_of ?? '', review.checked_at].sort().at(-1);
  }
  site.meta.entry_count = site.entries.length;
  site.coverage_by_category = [...site.entries.reduce((m,e)=>m.set(e.category,(m.get(e.category)??0)+1),new Map())].map(([category,count])=>({category,count})).sort((a,b)=>b.count-a.count||a.category.localeCompare(b.category,'ko'));
  if (ledger.reviews.length) site.meta.approved_reviews = {count:ledger.reviews.length, sha256:digest(ledger)};
  return site;
}
