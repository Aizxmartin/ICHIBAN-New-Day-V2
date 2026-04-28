"""
ICHIBAN INSIGHT - PDF/XPS Diagnostic Layer

This package classifies uploaded subject/market/AVM documents before extraction.
It does NOT attempt full valuation extraction. Its job is to route the file
to the correct parser or manual fallback path.
"""

from .document_source_probe import probe_document_source, DiagnosticResult

__all__ = ["probe_document_source", "DiagnosticResult"]
