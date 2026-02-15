"""1Stream (BVOIP) call recording integration module."""

from .client import OneStreamClient
from .mcp_tools import set_onestream_client

__all__ = ["OneStreamClient", "set_onestream_client"]
