"""Observability.

Week 2 wires OpenTelemetry spans around the agent loop and each tool call. The
eval runner already reports latency and cost per case, so the resume claim
("p95 Z ms, $A/request") has a source of truth before tracing lands.
"""

from psa.obs.trace import span

__all__ = ["span"]
