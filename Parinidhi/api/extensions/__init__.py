"""
Future Extension Interfaces for Forecast-Bust Sentinel (Day 6).

Defines typed abstract interfaces for future research components:
- OOD Abstention Engine
- Historical Analog Retrieval
- Multi-Model Disagreement
- Downstream RAG Explainer

CRITICAL: These are architecture hooks only. No fabricated values are generated.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class AbstractAbstentionEngine(ABC):
    """Abstract interface for Out-of-Distribution (OOD) detection and selective abstention."""

    @abstractmethod
    def evaluate_ood(self, features: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluate whether the forecast state falls outside the training distribution.
        
        Returns:
            Dict containing 'is_ood' (bool), 'ood_score' (float), 'abstain' (bool).
        """
        pass


class AbstractAnalogRetriever(ABC):
    """Abstract interface for historical meteorological analog case matching."""

    @abstractmethod
    def retrieve_analogs(self, features: Dict[str, Any], top_k: int = 3) -> List[Dict[str, Any]]:
        """
        Find historical atmospheric analogs for the current forecast regime.
        
        Returns:
            List of matching analog cases with dates, errors, and outcomes.
        """
        pass


class AbstractMultiModelComparator(ABC):
    """Abstract interface for multi-centre ensemble comparison (GEFS vs ECMWF vs NCMRWF)."""

    @abstractmethod
    def compare_ensembles(self, valid_time: str, location_id: str) -> Dict[str, Any]:
        """
        Compute inter-model disagreement metrics.
        """
        pass


class AbstractRAGExplainer(ABC):
    """
    Abstract interface for downstream natural language explanation retrieval.
    
    CRITICAL: RAG must NEVER generate or alter the numerical bust probability.
    It provides context only.
    """

    @abstractmethod
    def generate_narrative(self, risk_response: Dict[str, Any]) -> str:
        """
        Generate plain-language briefing for meteorologists based on calibrated risk outputs.
        """
        pass
