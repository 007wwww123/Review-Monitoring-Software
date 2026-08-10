"""Semantic-first cascaded fake-review detection package.

Heavy model classes intentionally remain in :mod:`spam_cascade.modeling` so
configuration and routing utilities can be used without importing PyTorch.
"""

from .config import CascadeConfig
from .routing import DecisionRouter

__all__ = ["CascadeConfig", "DecisionRouter"]
