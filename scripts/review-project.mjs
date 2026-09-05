// Private workbench bridge. Never included in the public bundle.
import { applyReviews, digest } from './review-overlay.mjs';
process.stdin.setEncoding('utf8');
let input = '';
for await (const chunk of process.stdin) input += chunk;
try {
  const {base, ledger} = JSON.parse(input);
  const site = applyReviews(base, ledger);
  process.stdout.write(JSON.stringify({site, hashes:Object.fromEntries(site.entries.map(e => [e.id,digest(e)]))}));
} catch { process.stderr.write('Review projection rejected\n'); process.exitCode = 2; }
