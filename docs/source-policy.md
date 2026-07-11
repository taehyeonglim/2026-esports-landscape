# Source policy

## Admission

Only publicly accessible HTTP(S) material may be fetched. No login, account, paywall bypass, credential, private endpoint, authenticated API, or browser-session collection is allowed. Before retrieval, honor applicable robots directives and source terms; a disallowance, unclear permission, or incompatible terms means do not fetch and record the reason for review.

A source is admitted only with its canonical public URL, publisher identity, retrieval time, provenance tier, and permitted-use decision. Unknown publishers and unknown policy values fail closed.

## Bounded retrieval

Use an allowlisted public redirect host. Follow at most five redirects; reject a redirect to a non-public or unallowlisted host. Request timeout is at most 60 seconds (the standard setting is 10), retries are bounded to three total retry attempts, and retry only transient failures with backoff. Reject bodies above 2 MB compressed or 8 MB decompressed (never configure above the implementation maxima of 20 MB and 100 MB respectively).

Do not log or retain response bytes. Retrieval bytes are transient input only: extract the minimum permitted facts, sanitize them, calculate permitted metadata/checksums, then discard the original body.

## Privacy and quarantine

Before any persistence, inspect extracted values for PII. For minors, do not persist names, handles, contact details, precise locations, schedules that identify a minor, or other identifying personal data. Store only the minimum non-identifying institutional or aggregate fact needed for the claim.

Suspicious, malformed, disallowed, oversized, PII-bearing, or policy-ambiguous material goes to opaque quarantine. Quarantine holds only an opaque case ID, reason code, timestamps, and safe diagnostic metadata—not the body, text excerpt, or PII—and cannot flow to publication without a new compliant retrieval and review.

## Corroboration and independence

A claim requiring corroboration needs two sources independent on **both** axes:

1. **Control axis:** distinct publisher-control clusters (owner, syndication network, or editorial control).
2. **Origin axis:** distinct reporting/original-information clusters.

Different URLs, domains, reposts, translations, wire copies, or syndicated articles do not establish independence when either axis is shared. An unregistered publisher cannot establish independence. Record the two cluster assignments with the decision.
