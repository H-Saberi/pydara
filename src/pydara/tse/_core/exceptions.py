"""Stable, explicit errors. A failed request is never an empty success."""

class PyDaraError(Exception):
    """Base error for this library."""

class ConfigurationError(PyDaraError, ValueError):
    """Report a configuration failure in PyDara operations."""
    pass

class InvalidArgumentError(PyDaraError, ValueError):
    """Report a invalidargument failure in PyDara operations."""
    pass

class NetworkError(PyDaraError):
    """Report a network failure in PyDara operations."""
    pass

class RequestBudgetExceededError(NetworkError):
    """Report a requestbudgetexceeded failure in PyDara operations."""
    pass

class OperationTimeoutError(NetworkError, TimeoutError):
    """Report a operationtimeout failure in PyDara operations."""
    pass

class ApiError(PyDaraError):
    """Report a api failure in PyDara operations."""
    def __init__(self, message: str, *, status_code: int | None = None):
        """Initialize the instance and its configured state.
        
        Args:
            message (str): Input for the __init__ operation.
            status_code (int | None): Input for the __init__ operation."""
        super().__init__(message)
        self.status_code = status_code

class AuthenticationError(ApiError):
    """Report a authentication failure in PyDara operations."""
    pass

class PermissionDeniedError(ApiError):
    """Report a permissiondenied failure in PyDara operations."""
    pass

class RateLimitError(ApiError):
    """Report a ratelimit failure in PyDara operations."""
    def __init__(self, message: str, *, retry_after: float | None = None):
        """Initialize the instance and its configured state.
        
        Args:
            message (str): Input for the __init__ operation.
            retry_after (float | None): Input for the __init__ operation."""
        super().__init__(message, status_code=429)
        self.retry_after = retry_after

class ServiceUnavailableError(ApiError):
    """Report a serviceunavailable failure in PyDara operations."""
    pass

class SchemaMismatchError(PyDaraError):
    """Report a schemamismatch failure in PyDara operations."""
    pass

class DataQualityError(PyDaraError):
    """Report a dataquality failure in PyDara operations."""
    pass

class UnknownInstrumentError(PyDaraError):
    """Report a unknowninstrument failure in PyDara operations."""
    pass

class AmbiguousInstrumentError(PyDaraError):
    """Report a ambiguousinstrument failure in PyDara operations."""
    def __init__(self, message: str, *, candidates: tuple[str, ...] = ()):
        """Initialize the instance and its configured state.
        
        Args:
            message (str): Input for the __init__ operation.
            candidates (tuple[str, ...]): Input for the __init__ operation."""
        super().__init__(message)
        self.candidates = candidates

class MissingValueError(PyDaraError):
    """Report a missingvalue failure in PyDara operations."""
    pass

class UnsupportedQuoteUnitError(PyDaraError):
    """Report a unsupportedquoteunit failure in PyDara operations."""
    pass

class UnsupportedCapabilityError(PyDaraError):
    """Report a unsupportedcapability failure in PyDara operations."""
    pass

class PointInTimeUnavailableError(UnsupportedCapabilityError):
    """Report a pointintimeunavailable failure in PyDara operations."""
    pass

class OfflineDataUnavailableError(PyDaraError):
    """Report a offlinedataunavailable failure in PyDara operations."""
    pass

class StaleDataError(PyDaraError):
    """Report a staledata failure in PyDara operations."""
    pass

class ClosedClientError(PyDaraError):
    """Report a closedclient failure in PyDara operations."""
    pass

class StorageError(PyDaraError):
    """Report a storage failure in PyDara operations."""
    def __init__(self, message: str, *, report=None):
        """Initialize the instance and its configured state.
        
        Args:
            message (str): Input for the __init__ operation.
            report (Any): Input for the __init__ operation."""
        super().__init__(message)
        self.report = report

class StorageFlushTimeout(StorageError, TimeoutError):
    """Encapsulate storage flush timeout behavior in the TSE module.
    
    This type is part of the documented implementation; consult field annotations and public API contracts for supported values."""
    pass

class UnknownReceiptError(StorageError):
    """Report a unknownreceipt failure in PyDara operations."""
    pass

class BatchDataError(PyDaraError):
    """Report a batchdata failure in PyDara operations."""
    def __init__(self, message: str, *, partial_result):
        """Initialize the instance and its configured state.
        
        Args:
            message (str): Input for the __init__ operation.
            partial_result (Any): Input for the __init__ operation."""
        super().__init__(message)
        self.partial_result = partial_result

class DaraWarning(UserWarning):
    """Encapsulate dara warning behavior in the TSE module.
    
    This type is part of the documented implementation; consult field annotations and public API contracts for supported values."""
    pass

class StorageWarning(DaraWarning):
    """Encapsulate storage warning behavior in the TSE module.
    
    This type is part of the documented implementation; consult field annotations and public API contracts for supported values."""
    pass

class StaleDataWarning(DaraWarning):
    """Encapsulate stale data warning behavior in the TSE module.
    
    This type is part of the documented implementation; consult field annotations and public API contracts for supported values."""
    pass


class CoverageError(PyDaraError):
    """Report a coverage failure in PyDara operations."""
    def __init__(self, message: str, *, report=None):
        """Initialize the instance and its configured state.
        
        Args:
            message (str): Input for the __init__ operation.
            report (Any): Input for the __init__ operation."""
        super().__init__(message)
        self.report = report


class OptionalDependencyError(PyDaraError, ImportError):
    """Report a optionaldependency failure in PyDara operations."""
    pass

class FileExistsDataError(StorageError, FileExistsError):
    """Report a fileexistsdata failure in PyDara operations."""
    pass

class StorageBusyError(StorageError):
    """Report a storagebusy failure in PyDara operations."""
    pass

class IntegrityError(StorageError):
    """Report a integrity failure in PyDara operations."""
    pass
