"""Results for multi-instrument history. Tables remain ordinary Pandas frames."""
from __future__ import annotations
from dataclasses import dataclass, field
import pandas as pd


@dataclass(frozen=True, kw_only=True)
class BatchFrames:
    """History rows, item errors, and one summary per requested input.

    ``request_index`` preserves input order/duplicates, including empty successes.
    Frozen only prevents attribute rebinding; callers can edit their own frames.
    """
    data: pd.DataFrame
    errors: pd.DataFrame
    requests: pd.DataFrame
    manifest: dict = field(default_factory=dict)
