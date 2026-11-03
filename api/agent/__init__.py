"""Haske investigator: an agentic escalation layer over the deterministic pipeline.

The driver model (Meta Muse Spark) decides which tools to call and perceives the label.
Deterministic code decides every verdict code and fact. Tool results are the only source
of NRNs, URLs, alert text, and registry data. Label text is untrusted data, never
instructions.
"""

from .loop import AgentOutcome, run_agent
from .tools import TOOLS, AgentContext

__all__ = ["AgentOutcome", "run_agent", "TOOLS", "AgentContext"]
