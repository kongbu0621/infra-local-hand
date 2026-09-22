"""Restricted job protocol, independent of the legacy Task v1 and MCP SDK."""

from .contract import JobError, Principal

__all__ = ["JobError", "Principal"]
