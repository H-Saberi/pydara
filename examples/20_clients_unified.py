"""Synthetic-safe usage pattern; actual market fetch requires an exchange connection."""
from pydara import tse

# Obtain explicit instruments before querying their individual/institutional records.
selected = tse.assets(ins_code=["46348559193224090"])
traders = tse.traders(
    assets=selected,
    start="1403-01-01", end="1403-12-29", calendar="jalali",
    on_multiple="all", on_conflict="error", on_error="collect",
)
print(traders.columns.tolist())
print(traders.attrs["pydara"]["errors"])
