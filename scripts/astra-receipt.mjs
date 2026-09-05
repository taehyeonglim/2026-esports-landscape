import { createHash, generateKeyPairSync, sign, verify } from 'node:crypto';
import { readFileSync, writeFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

export function canonical(value) {
  return JSON.stringify(value, (_, item) => item && typeof item === 'object' && !Array.isArray(item)
    ? Object.fromEntries(Object.keys(item).sort().map(key => [key, item[key]])) : item);
}
export const digest = value => createHash('sha256').update(canonical(value)).digest('hex');
const requireValue = (condition, message) => { if (!condition) throw new Error(`AI release gate: ${message}`); };
const exactKeys = (value, keys) => value && typeof value === 'object' && !Array.isArray(value)
  && Object.keys(value).sort().join(',') === [...keys].sort().join(',');
const shortText = (value, max = 2000) => typeof value === 'string' && value.trim().length > 0 && value.length <= max;

export function validateReview(review, policy) {
  requireValue(exactKeys(review, ['verdict', 'summary', 'checks', 'blockers', 'limitations']), 'invalid review shape');
  requireValue(review.verdict === 'approved', 'model did not approve');
  requireValue(shortText(review.summary), 'missing review summary');
  requireValue(Array.isArray(review.blockers) && review.blockers.length === 0, 'unresolved model blockers');
  requireValue(Array.isArray(review.limitations) && review.limitations.length <= 20 && review.limitations.every(item => shortText(item)), 'invalid limitations');
  requireValue(Array.isArray(review.checks) && review.checks.length === policy.required_checks.length, 'incomplete checks');
  requireValue(new Set(review.checks.map(item => item.id)).size === policy.required_checks.length, 'duplicate checks');
  for (const item of review.checks) {
    requireValue(exactKeys(item, ['id', 'passed', 'reason']) && policy.required_checks.includes(item.id)
      && item.passed === true && shortText(item.reason), 'failed or malformed check');
  }
  return review;
}

export function signReceipt(payload, privateKey) {
  return { payload, signature: sign(null, Buffer.from(canonical(payload)), privateKey).toString('base64') };
}

export function verifyReceipt(receipt, { policy, publicKey, sourceSha, releaseId, repository, now = Date.now() }) {
  requireValue(policy.enabled === true && policy.authority === 'repository_owner_delegated_ai', 'AI authority not enabled');
  requireValue(exactKeys(receipt, ['payload', 'signature']), 'invalid receipt shape');
  requireValue(typeof receipt.signature === 'string' && /^[A-Za-z0-9+/]{86}==$/.test(receipt.signature), 'invalid signature encoding');
  const payload = receipt.payload;
  requireValue(verify(null, Buffer.from(canonical(payload)), publicKey, Buffer.from(receipt.signature, 'base64')), 'invalid signature');
  requireValue(exactKeys(payload, ['schema_version', 'repository', 'source_sha', 'release_id', 'policy_sha256', 'evidence_sha256',
    'issued_at', 'expires_at', 'model', 'reasoning_effort', 'transport', 'cli_version', 'session_id', 'review']), 'invalid signed payload');
  requireValue(payload.schema_version === 1 && payload.repository === repository && repository === policy.repository, 'repository mismatch');
  requireValue(/^[a-f0-9]{40}$/.test(sourceSha) && payload.source_sha === sourceSha, 'source commit mismatch');
  requireValue(/^[a-f0-9]{64}$/.test(releaseId) && payload.release_id === releaseId, 'rebuilt release mismatch');
  requireValue(payload.policy_sha256 === digest(policy), 'review policy changed');
  requireValue(/^[a-f0-9]{64}$/.test(payload.evidence_sha256), 'missing evidence digest');
  requireValue(payload.model === policy.model && payload.reasoning_effort === policy.reasoning_effort && payload.transport === policy.transport,
    'wrong model or execution mode');
  requireValue(shortText(payload.cli_version, 100) && shortText(payload.session_id, 100), 'missing execution identity');
  const issued = Date.parse(payload.issued_at);
  const expires = Date.parse(payload.expires_at);
  requireValue(Number.isFinite(issued) && Number.isFinite(expires) && issued <= now + policy.clock_skew_seconds * 1000
    && expires > now && expires > issued && expires - issued <= policy.max_age_seconds * 1000, 'expired or invalid review window');
  return validateReview(payload.review, policy);
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  try {
    const command = process.argv[2];
    const argument = name => {
      const index = process.argv.indexOf(name);
      if (index < 0 || !process.argv[index + 1]) throw new Error(`Missing ${name}`);
      return process.argv[index + 1];
    };
    const readJson = name => JSON.parse(readFileSync(argument(name), 'utf8'));
    if (command === 'keygen') {
      const { privateKey, publicKey } = generateKeyPairSync('ed25519');
      writeFileSync(argument('--private'), privateKey.export({ type: 'pkcs8', format: 'pem' }), { mode: 0o600, flag: 'wx' });
      writeFileSync(argument('--public'), publicKey.export({ type: 'spki', format: 'pem' }), { mode: 0o644, flag: 'wx' });
    } else if (command === 'sign') {
      const payload = readJson('--payload');
      const policy = readJson('--policy');
      validateReview(payload.review, policy);
      writeFileSync(argument('--output'), `${JSON.stringify(signReceipt(payload, readFileSync(argument('--private'))), null, 2)}\n`, { mode: 0o600 });
    } else if (command === 'verify') {
      const receipt = process.env.ASTRA_REVIEW_RECEIPT
        ? JSON.parse(Buffer.from(process.env.ASTRA_REVIEW_RECEIPT, 'base64').toString('utf8')) : readJson('--receipt');
      const policy = readJson('--policy');
      const result = verifyReceipt(receipt, { policy, publicKey: process.env.ASTRA_REVIEW_PUBLIC_KEY || readFileSync(argument('--public')),
        sourceSha: process.env.SOURCE_REF || argument('--source'), releaseId: process.env.RELEASE_ID || argument('--release'),
        repository: process.env.GITHUB_REPOSITORY || policy.repository });
      console.log(JSON.stringify({ authority: policy.authority, model: policy.model, verdict: result.verdict, source: receipt.payload.source_sha }));
    } else throw new Error('Unsupported receipt command');
  } catch (error) {
    console.error(error.message);
    process.exitCode = 1;
  }
}
