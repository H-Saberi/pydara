"""Repository port for a future PostgreSQL adapter (not implemented)."""
from typing import Protocol
import pandas as pd

class HistoryRepository(Protocol):
    """Describe the required interface for local history repositories.
    
    This type is part of the documented implementation; consult field annotations and public API contracts for supported values."""
    def read(self, instrument, *, start=None, end=None, calendar='gregorian',
             include_jdate=False, as_of=None) -> pd.DataFrame:
        """Read the requested value.
        
        Args:
            instrument (Any): Instrument name or explicit instrument reference; ambiguity is not silently resolved.
            start (Any): Optional beginning of the requested date range.
            end (Any): Optional end of the requested date range.
            calendar (Any): Calendar used to parse or format dates.
            include_jdate (Any): Input for the read operation.
            as_of (Any): Requested economic effective date; check endpoint support.
        
        Returns:
            pd.DataFrame: Result of the read operation; refer to its public API contract for schema details."""
        ...
    def status(self) -> pd.DataFrame:
        """Return status for the requested value.
        
        Returns:
            pd.DataFrame: Result of the status operation; refer to its public API contract for schema details."""
        ...
    def revisions(self, instrument, *, start=None, end=None, calendar='gregorian') -> pd.DataFrame:
        """Perform the revisions operation.
        
        Args:
            instrument (Any): Instrument name or explicit instrument reference; ambiguity is not silently resolved.
            start (Any): Optional beginning of the requested date range.
            end (Any): Optional end of the requested date range.
            calendar (Any): Calendar used to parse or format dates.
        
        Returns:
            pd.DataFrame: Result of the revisions operation; refer to its public API contract for schema details."""
        ...
    def batch_report(self, request_id) -> dict | None:
        """Perform the batch report operation.
        
        Args:
            request_id (Any): Input for the batch_report operation.
        
        Returns:
            dict | None: Result of the batch_report operation; refer to its public API contract for schema details."""
        ...
    def reindex(self) -> dict:
        """Reindex the requested value.
        
        Returns:
            dict: Result of the reindex operation; refer to its public API contract for schema details."""
        ...
