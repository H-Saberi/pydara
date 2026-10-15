# SQLite storage and revision semantics

Existing tables: response_versions, observations, latest_response. They remain readable by earlier releases. Part 3 adds:

| Table | Key | Role |
|---|---|---|
| dara_history_meta | id=1 | independent normalized-schema version |
| dara_history_batches | batch_id=request_id | fetch context, identity annotations, commit and counters |
| dara_daily_versions | scope, instrument, date, version hash | immutable business row contents |
| dara_daily_observations | batch_id, date | observation of a particular version |
| dara_daily_latest | scope, instrument, date | most recently fetched committed observation |

The existing worker performs normalization and all index writes in the same transaction as the response. No second unbounded worker or queue is added. Online code never waits on normalization or index writes. Explicit `flush`, local reads, `sync_history(wait=True)`, `save`, and `reindex_history` necessarily may wait and report failure.

The business version identity is inherited from Part 2: verified instrument, date, raw numeric fields, count and source timestamp. Container record IDs and library retrieval times are not business prices. A source timestamp-only change therefore can create another row version. This definition is versioned; it is not a claim that the exchange assigned the hash.

A -> B -> A example: two economic contents, three observations, latest pointer A. Choosing by first-seen hash alone would incorrectly return B; reads choose the latest eligible observation instead. Out-of-order writes cannot move the latest pointer backwards. Conflicting contents with the same exact observation time fail rather than selecting an arbitrary winner.

`available_at` on stored rows is max(fetched_at, committed_at). Source publication time is still unknown. Metadata derived from current instrument info remains marked. Any point-in-time selection is relative to observations retained by this local installation, not the source's historical publication timeline.

A full-response omission does not constitute a deletion instruction. Old rows remain available with an omission flag until a separate, evidence-backed reconciliation policy is implemented. Likewise, absence of a trading date is not automatically a holiday, stop, zero price, or zero return.

Recovery: raw v0.2 observations are indexed explicitly with reindex_history(). It reads cached packets one at a time; completed batches survive interruption. Do not change user_version manually or erase the database. There is no automatic destructive migration or schema downgrade.

SQLite is a local-file backend; use a local filesystem. WAL does not remove the one-writer rule and does not make network shares a supported storage location. A PostgreSQL repository can be added behind the documented storage contracts later; no PostgreSQL driver/configuration is shipped as working code here.
