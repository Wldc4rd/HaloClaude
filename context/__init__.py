"""
Context injection module for HaloClaude.

Provides automatic pre-fetching and injection of Halo context
(ticket, user, client, assets) into Claude's system prompt.
"""

from .parser import TicketIdParser
from .fetcher import ContextFetcher, ContextData
from .formatter import ContextFormatter
from .injector import ContextInjector

__all__ = [
    "TicketIdParser",
    "ContextFetcher",
    "ContextData",
    "ContextFormatter",
    "ContextInjector",
]
