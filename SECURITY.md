# Security and operational notes

No API credentials are needed or accepted in this release. No telemetry, trading,
account access, proxy rotation, TLS bypass, or package auto-update is performed.
Requests target a fixed HTTPS base URL; redirects are not followed. Response
bytes are capped; malformed JSON and duplicate keys are rejected. Only validated
responses enter the cache. Never send credentials or tokens in issue reports.

Do not treat a fresh retrieval timestamp as proof of fresh exchange data.
Unit normalization is deliberately narrow and unverified instruments carry
unknown units. The fixture suite is not an independent security audit.

No background network polling is started. The optional background writer only
persists data already obtained by an explicit user operation. Stop/close clients
when finished, and explicitly flush when durability is required.

The supplied license covers code, not permission to redistribute exchange data.
A public endpoint does not imply unlimited access or a service-level guarantee.

Daily-history cache versions are response observations, not certified publication history.
Do not use raw or retroactively adjusted daily data as point-in-time ML evidence.

Part 3 adds inert tagged serialization, not pickle or eval. Structural dtype
parsing uses an allowlist. Hashes detect accidental corruption, not malicious
rewriting of data and hashes together. XLSX formulas are not executed;
metadata is not encrypted. CSV+sidecar are two files, not an atomic pair.
Readers are eager and file-size limits are not a universal sandbox against
all compressed-format resource-exhaustion attacks. Only open trusted archives.

Normalized history stores observation versions. `committed_at` is the writer's
transaction timestamp, not a metrologically precise post-fsync timestamp.
Local as_of is based on recorded timestamps and does not certify an exchange
publication time or a sub-second, crash-consistent replay of database visibility.
