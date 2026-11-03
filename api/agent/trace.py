"""Agent trace: one event per tool call with effort, latency, and token use."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TraceEvent:
    round: int
    tool: str
    effort: str
    latency_ms: int
    tokens: int
    status: str  # "ok" | "error" | "invalid_retry"
    summary: str

    def to_dict(self) -> dict:
        return {
            "round": self.round,
            "tool": self.tool,
            "effort": self.effort,
            "latency_ms": self.latency_ms,
            "tokens": self.tokens,
            "status": self.status,
            "summary": self.summary,
        }


@dataclass
class AgentTrace:
    events: list[TraceEvent] = field(default_factory=list)

    def add(self, **kw) -> None:
        self.events.append(TraceEvent(**kw))

    def to_list(self) -> list[dict]:
        return [e.to_dict() for e in self.events]

    @property
    def total_tokens(self) -> int:
        return sum(e.tokens for e in self.events)

    @property
    def total_calls(self) -> int:
        return len(self.events)

    def summary_line(self) -> str:
        if not self.events:
            return "no agent tool calls"
        tools = [e.tool for e in self.events]
        reads = sum(1 for t in tools if t == "read_label")
        alerts = sum(1 for t in tools if t == "alert_search")
        parts = [f"{len(tools)} tool calls"]
        if reads:
            parts.append(f"{reads} reads")
        if alerts:
            parts.append(f"{alerts} alert searches")
        return ", ".join(parts)
