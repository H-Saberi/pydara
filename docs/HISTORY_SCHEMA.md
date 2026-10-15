# DailyBar table, schema version 1

All columns exist for empty results too. No user DataFrame is stored by
reference: raw immutable response bytes are enqueued before the table is
returned. Changing the table cannot mutate the cache.

| Column/group | Dtype / meaning |
|---|---|
| date | datetime64[ns], Gregorian day with no timezone |
| jdate (opt-in) | string, YYYY-MM-DD Jalali |
| ins_code | string, positively validated requested listing ID |
| symbol, raw_symbol | string, identity observed via current info; NOT proof of historical name |
| instrument_id, company_cisin | separate string identities |
| open_price, high_price, low_price | raw priceFirst, priceMax, priceMin |
| last_price | raw pDrCotVal, not the closing-price calculation |
| closing_price | raw pClosing, NOT corporate-action-adjusted close |
| previous_reference_price | raw priceYesterday; need not equal previous row closing |
| volume, turnover | raw qTotTran5J, qTotCap |
| trade_count | nullable Int64 from zTotTran |
| prices and amounts | Float64 by default; Decimal/object in ClientConfig(numeric='exact') |
| currency, quote_unit, quantity_unit | identity-derived explicit unit context; unknown retained |
| adjustment, series | none, listing |
| raw_ins_code | source value retained separately; may be zero/missing |
| source_record_id | source id if supplied, string |
| source, endpoint_id, scope_id | provenance; sample/public never intermixed |
| row_id | hash(scope, canonical code, day), stable economic row identity |
| row_version_id | hash of normalized economic content and source timestamp |
| observation_id | request ID |
| payload_hash / raw_reference | SHA256 of exact received response bytes |
| fetched_at | UTC observed request time |
| first_observed_at | first known observation of whole response bytes, NOT each historical row |
| available_at | conservative current response observation time, NOT trading date |
| source_timestamp | dEven + hEven interpreted in Asia/Tehran and converted to UTC |
| identity_fetched_at | observation time of the current instrument info |
| availability_basis | observed_response; publication timestamps unavailable |
| storage_receipt_id | pending/finished autosave can be inspected separately |
| from_cache, is_stale | nullable booleans |
| quality_flags | tuple of explicit observations |

`hEven` is a source timestamp of unverified exact semantics, not asserted to
be last-trade/publication/finalization time. A date equal to retrieval date
gets `current_session_row_not_certified_final` regardless of `iClose/yClose`:
those flags' economic semantics were not independently confirmed here.

## Validation / empty semantics

Mandatory fields: dEven, pDrCotVal, pClosing. Optional numerical fields that
are absent/null become NA, never zero. Zero prices/volume are retained with
flags because source conventions for no-trade days are not inferred.

A missing/null root is SchemaMismatchError; a real empty list is a typed empty
success. Identical duplicate days collapse with a flag/count. Conflicting
days are DataQualityError, never an arbitrary last-row winner.

A zero/missing response insCode is accepted only after independent instrument
info verification; the canonical code still comes from that verification.
A positive mismatched or fractional ID remains an error. This extends the
observed Part 1 placeholder behavior, not the global identifier parser.

Float64 can approximate monetary values. Values larger than 2**53 are flagged
and overflow to infinity is refused. Use exact mode when decimal fidelity is
required. The decimal digit/exponent guards prevent malicious expansion.

## Metadata / coverage

`df.attrs['pydara']` contains requested, source-observed and returned ranges;
row counts; duplicate counts; empty reason; endpoint and storage references;
cache freshness; numerical profile and warnings. attrs is a convenience, not
an immutable audit record; arbitrary Pandas operations may remove it.

coverage_status is ALWAYS `unknown` for this public endpoint. Dates alone do
not prove exhaustive trading sessions, initial listing coverage, or deletion
history. FetchPolicy(coverage='raise') rejects this uncertainty explicitly.
