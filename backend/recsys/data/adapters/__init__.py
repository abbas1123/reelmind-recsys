"""Dataset adapters. Importing this package registers every built-in adapter."""

from recsys.data.adapters import movielens  # noqa: F401
from recsys.data.adapters.base import DatasetAdapter, RawDataset, get_adapter, registered_adapters

__all__ = ["DatasetAdapter", "RawDataset", "get_adapter", "registered_adapters"]
