"""PyDara: financial data modules. Importing PyDara has no external side effects."""
from importlib import import_module

__version__ = "0.7.3a6"
__all__ = ["tse", "__version__"]


def __getattr__(name: str):
    """Lazily expose the supported TSE submodule without eager importing.
    
    Args:
        name (str): Input for the __getattr__ operation.
    
    Returns:
        Implementation-defined result or generator output; see the calling API.
    
    Raises:
        AttributeError: When the corresponding validation or operation fails."""
    if name == "tse":
        module = import_module("pydara.tse")
        globals()[name] = module
        return module
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
