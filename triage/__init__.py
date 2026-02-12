"""Ticket pipeline module (triage + review)."""

from .pipeline import run_ticket_pipeline

# Backwards compatibility
run_triage_pipeline = run_ticket_pipeline

__all__ = ["run_ticket_pipeline", "run_triage_pipeline"]
