"""Orchestrator and Markdown report."""

from __future__ import annotations

from .agents import CoachAgent, ExtractorAgent, MatcherAgent, MatchState, ReviewerAgent
from .llm import LLMClient


def run_pipeline(resume: str, job: str, llm: LLMClient | None = None) -> MatchState:
    state = MatchState(resume=resume, job=job)
    # The reviewer always runs rule-based: a guardrail shouldn't depend on the model it checks.
    for agent in (ExtractorAgent(llm), MatcherAgent(), CoachAgent(llm), ReviewerAgent()):
        state = agent(state)
    return state


def to_markdown(state: MatchState) -> str:
    def bullets(items):
        return "\n".join(f"- {i}" for i in items) or "- (none)"

    lines = [
        "# Job match report",
        "",
        f"**Match score: {state.score}/100**",
        "",
        "| Component | Score |",
        "|---|---|",
        *[f"| {k.replace('_', ' ')} | {v:.0%} |" for k, v in state.breakdown.items()],
        "",
        f"Experience: {state.candidate_years:g} years (role asks for {state.required_years:g}+)",
        "",
        "## Matched skills",
        bullets(f"**{s}** — {state.candidate_skills[s][0]}" for s in state.matched),
        "",
        "## Gaps",
        bullets(f"{s} ({'required' if s in state.required else 'preferred'})" for s in state.gaps),
        "",
        "## Suggestions",
        bullets(f"[{s.kind}] {s.text}" for s in state.suggestions),
    ]
    if state.rejected:
        lines += ["", "## Blocked by reviewer (unsupported by resume)",
                  bullets(f"{s.skill}: {s.text}" for s in state.rejected)]
    lines += ["", "<details><summary>Agent trace</summary>", "", bullets(state.trace), "", "</details>"]
    return "\n".join(lines) + "\n"
