import test from 'node:test';
import assert from 'node:assert/strict';
import { generateKeyPairSync } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { digest, signReceipt, verifyReceipt } from '../scripts/astra-receipt.mjs';
const policy = JSON.parse(readFileSync('config/astra-review-policy.v1.json'));
const { privateKey, publicKey } = generateKeyPairSync('ed25519');
const now = Date.now();
const payload = { schema_version: 1, repository: policy.repository, source_sha: 'a'.repeat(40), release_id:'b'.repeat(64), policy_sha256:digest(policy), evidence_sha256:'c'.repeat(64), issued_at:new Date(now).toISOString(), expires_at:new Date(now+3600000).toISOString(), model:policy.model, reasoning_effort:policy.reasoning_effort, transport:policy.transport, cli_version:'test', session_id:'test', review:{verdict:'approved',summary:'Verified',checks:policy.required_checks.map(id=>({id,passed:true,reason:'Evidence passed'})),blockers:[],limitations:[]}};
const options = {policy,publicKey,sourceSha:payload.source_sha,releaseId:payload.release_id,repository:policy.repository,now};
test('signed approval accepts exact build only',()=>assert.equal(verifyReceipt(signReceipt(payload,privateKey),options).verdict,'approved'));
for (const [name, mutate] of Object.entries({ rejected:p=>p.review.verdict='rejected', blocker:p=>p.review.blockers.push('block'), missing:p=>p.review.checks.pop(), duplicate:p=>p.review.checks[0]=p.review.checks[1], wrongModel:p=>p.model='other', wrongCommit:p=>p.source_sha='d'.repeat(40), wrongBuild:p=>p.release_id='e'.repeat(64), expired:p=>p.expires_at=new Date(now-1).toISOString(), policy:p=>p.policy_sha256='f'.repeat(64) })) {
 test(`rejects ${name}`,()=>{const p=structuredClone(payload);mutate(p);assert.throws(()=>verifyReceipt(signReceipt(p,privateKey),options));});
}
test('rejects tampering and missing receipts',()=>{const r=signReceipt(payload,privateKey);r.payload=structuredClone(payload);r.payload.review.summary='tampered';assert.throws(()=>verifyReceipt(r,options));assert.throws(()=>verifyReceipt({},options));});
