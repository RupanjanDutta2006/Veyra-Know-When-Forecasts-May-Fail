"""Authoritative Provider Registry for Veyra Phase 3 Day 37 (Gate C7).

Manages registration, lookup, and selection of forecast provider adapters.

SCIENTIFIC GOVERNANCE INVARIANTS:
1. Explicit Failure on Unknown Provider: Requesting an unknown provider identifier raises an explicit `UnknownProviderError` instead of silently falling back to default.
2. Backward-Compatible Default: Querying without specifying a provider ID defaults to `openmeteo_gefs`.
3. Multi-Provider Enumeration: Provides listing of registered adapters and their operational modes.
"""
import logging
from typing import Dict, List, Optional

from backend.app.adapters.fixture_second_provider_adapter import FixtureSecondProviderAdapter
from backend.app.adapters.openmeteo_adapter import OpenMeteoProviderAdapter
from backend.app.adapters.provider_adapter import BaseProviderAdapter

logger = logging.getLogger(__name__)


class UnknownProviderError(KeyError):
    """Raised when an unrecognized provider identifier is requested."""

    pass


class ProviderRegistry:
    """Thread-safe registry for forecast provider adapters."""

    def __init__(self, register_defaults: bool = True):
        self._registry: Dict[str, BaseProviderAdapter] = {}
        if register_defaults:
            self._register_default_adapters()

    def _register_default_adapters(self) -> None:
        """Register primary Open-Meteo adapter and secondary fixture provider adapter."""
        openmeteo = OpenMeteoProviderAdapter()
        fixture_sec = FixtureSecondProviderAdapter()
        self.register(openmeteo)
        self.register(fixture_sec)

    def register(self, adapter: BaseProviderAdapter) -> None:
        """Register a provider adapter."""
        pid = adapter.provider_id.strip().lower()
        self._registry[pid] = adapter
        logger.info("Registered forecast provider adapter '%s' (%s)", pid, adapter.provider_name)

    def get(self, provider_id: Optional[str] = None) -> BaseProviderAdapter:
        """Retrieve a registered provider adapter by ID.

        Args:
            provider_id: Unique provider identifier. If None or blank, returns default 'openmeteo_gefs'.

        Returns:
            BaseProviderAdapter instance.

        Raises:
            UnknownProviderError: If an explicit non-existent provider ID is requested.
        """
        if not provider_id or not str(provider_id).strip():
            # Default to primary Open-Meteo provider for backward compatibility
            return self._registry["openmeteo_gefs"]

        clean_pid = str(provider_id).strip().lower()
        if clean_pid not in self._registry:
            raise UnknownProviderError(
                f"Unknown forecast provider '{provider_id}'. "
                f"Registered providers: {list(self._registry.keys())}"
            )
        return self._registry[clean_pid]

    def list_providers(self) -> List[Dict[str, str]]:
        """List metadata for all registered provider adapters."""
        return [
            {
                "provider_id": adapter.provider_id,
                "provider_name": adapter.provider_name,
                "provider_source_mode": adapter.provider_source_mode.value,
            }
            for adapter in self._registry.values()
        ]


# Authoritative global singleton registry instance
default_provider_registry = ProviderRegistry()
