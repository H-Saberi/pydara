> Upstream references for the TSE data implementation retained in PyDara. See README_FA.md in the project root, API_REFERENCE.md and MIGRATION_FA.md for current usage.

# Sources and evidence boundary

Design basis: user-supplied `pydara_architecture_reference_v0_2.zip`.
Reviewed on 2026-10-13. This implementation uses public HTTP endpoints, not either
reference library as a dependency. It was written independently.

## Endpoint evidence

- `GET Instrument/GetInstrumentSearch/{query}`: identity candidates;
  root `instrumentSearch`, list. Query is URL-encoded; no first-result selection.
- `GET Instrument/GetInstrumentInfo/{ins_code}`: root `instrumentInfo`, object.
- `GET ClosingPrice/GetClosingPriceInfo/{ins_code}`: root `closingPriceInfo`, object.
- Base: `https://cdn.tsetmc.com/api/`

Existing reference: `tsetmc` 5.1.0 source, commit
`af5f4578fe4a21030759c8ed1cef3f72a00834ab`, file `tsetmc/instruments.py`.
https://github.com/5j9/tsetmc/blob/af5f4578fe4a21030759c8ed1cef3f72a00834ab/tsetmc/instruments.py

A published sample of instrument-info shape and the 300 share type:
https://pypi.org/project/tsetmc/0.50.0/

Narrow yVal reference (300/TSE shares, 303/IFB shares, 309/base shares):
https://github.com/m-ahmadi/tse-client/blob/master/README.md
This is community source evidence, not a current official schema guarantee.
The inferred IRR/share unit mapping is recorded in result assumptions. Other
instrument types are not automatically assigned a currency or quantity unit.

## Infrastructure

https://www.python-httpx.org/advanced/transports/
https://www.python-httpx.org/async/
https://www.python-httpx.org/advanced/clients/
https://www.sqlite.org/wal.html
https://packaging.python.org/en/latest/tutorials/packaging-projects/

## Not verified

Live requests to the TSETMC CDN failed in the build environment (network/DNS
access unavailable; browser requests also failed). All included exchange payloads
are explicitly SYNTHETIC fixtures, not captured live responses. API behavior on
the user's network, data completeness, server limits, terms and permissions,
Windows/Python 3.14 execution, and real brokerage-level correctness remain
unverified. No endpoint is represented as live-tested.
