"""Four cooperating agents that share one state object.

Extractor -> Matcher -> Coach -> Reviewer

Each agent can run deterministically (rules + taxonomy) or with an LLM. The
Reviewer is a guardrail: it rejects any coaching suggestion that would claim a
skill the candidate's resume gives no evidence for.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field

from .llm import LLMClient
from .skills import TAXONOMY, find_skills

_YEARS = re.compile(r"(\d{1,2})\s*\+?\s*(?:years|yrs)", re.IGNORECASE)
_PREFERRED_HEADINGS = re.compile(r"^(nice to have|preferred|bonus|plus)\b", re.IGNORECASE)
_REQUIRED_HEADINGS = re.compile(r"^(requirements|required|must have|qualifications|what you.ll need)\b",
                                re.IGNORECASE)
_DATE_RANGE = re.compile(r"\b(19|20)(\d{2})\s*[-–]\s*(?:(19|20)(\d{2})|present|current)\b", re.IGNORECASE)


@dataclass
class Suggestion:
    kind: str          # "add_evidence" | "learn" | "reframe"
    skill: str
    text: str


@dataclass
class MatchState:
    resume: str
    job: str
    candidate_skills: dict[str, list[str]] = field(default_factory=dict)
    required: list[str] = field(default_factory=list)
    preferred: list[str] = field(default_factory=list)
    candidate_years: float = 0.0
    required_years: float = 0.0
    score: float = 0.0
    breakdown: dict[str, float] = field(default_factory=dict)
    matched: list[str] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)
    suggestions: list[Suggestion] = field(default_factory=list)
    rejected: list[Suggestion] = field(default_factory=list)
    trace: list[str] = field(default_factory=list)


class Agent:
    name = "agent"

    def __init__(self, llm: LLMClient | None = None):
        self.llm = llm

    def __call__(self, state: MatchState) -> MatchState:
        start = time.perf_counter()
        self.run(state)
        state.trace.append(f"{self.name}: {(time.perf_counter() - start) * 1000:.1f} ms"
                           + (" (llm)" if self.llm else " (rules)"))
        return state

    def run(self, state: MatchState) -> None:  # pragma: no cover - interface
        raise NotImplementedError


# ------------------------------------------------------------------ extractor
def _split_job_sections(job: str) -> tuple[str, str]:
    required: list[str] = []
    preferred: list[str] = []
    current = required
    for line in job.splitlines():
        heading = line.strip().rstrip(":")
        if _PREFERRED_HEADINGS.match(heading):
            current = preferred
            continue
        if _REQUIRED_HEADINGS.match(heading):
            current = required
            continue
        current.append(line)
    return "\n".join(required), "\n".join(preferred)


def _resume_years(resume: str) -> float:
    stated = [int(m) for m in _YEARS.findall(resume)]
    if stated:
        return float(max(stated))
    spans = []
    for m in _DATE_RANGE.finditer(resume):
        start = int(m.group(1) + m.group(2))
        end = int(m.group(3) + m.group(4)) if m.group(4) else 2026
        spans.append((start, end))
    return float(sum(max(0, e - s) for s, e in spans))


class ExtractorAgent(Agent):
    name = "extractor"

    def run(self, state: MatchState) -> None:
        state.candidate_skills = find_skills(state.resume)
        required_text, preferred_text = _split_job_sections(state.job)
        if self.llm:
            data = json.loads(self.llm.complete(
                "Extract skills from a job description. Use only these canonical names: "
                + ", ".join(TAXONOMY) + '. Reply as JSON: {"required": [...], "preferred": [...]}',
                state.job))
            state.required = [s for s in data.get("required", []) if s in TAXONOMY]
            state.preferred = [s for s in data.get("preferred", []) if s in TAXONOMY and s not in state.required]
        else:
            state.required = sorted(find_skills(required_text))
            state.preferred = sorted(set(find_skills(preferred_text)) - set(state.required))
        years = [int(y) for y in _YEARS.findall(required_text)]
        state.required_years = float(min(years)) if years else 0.0
        state.candidate_years = _resume_years(state.resume)


# -------------------------------------------------------------------- matcher
class MatcherAgent(Agent):
    """Weighted score: 70% required skills, 20% preferred skills, 10% experience."""
    name = "matcher"

    def run(self, state: MatchState) -> None:
        have = set(state.candidate_skills)
        req_hit = [s for s in state.required if s in have]
        pref_hit = [s for s in state.preferred if s in have]
        req = len(req_hit) / len(state.required) if state.required else 1.0
        pref = len(pref_hit) / len(state.preferred) if state.preferred else 1.0
        exp = min(1.0, state.candidate_years / state.required_years) if state.required_years else 1.0
        state.breakdown = {"required_skills": round(req, 3), "preferred_skills": round(pref, 3),
                           "experience": round(exp, 3)}
        state.score = round(100 * (0.7 * req + 0.2 * pref + 0.1 * exp), 1)
        state.matched = req_hit + pref_hit
        state.gaps = [s for s in state.required + state.preferred if s not in have]


# ---------------------------------------------------------------------- coach
class CoachAgent(Agent):
    name = "coach"

    def run(self, state: MatchState) -> None:
        for skill in state.matched:
            evidence = state.candidate_skills[skill]
            if all(len(line) < 40 for line in evidence):  # only listed, never shown in action
                state.suggestions.append(Suggestion(
                    "add_evidence", skill,
                    f"{skill} only appears in a skills list. Add a bullet that shows it in a project "
                    f"with a measurable result."))
        for skill in state.gaps:
            priority = "required" if skill in state.required else "preferred"
            state.suggestions.append(Suggestion(
                "learn", skill,
                f"No evidence of {skill} ({priority}). Build a small project with it, or don't claim it."))
        if self.llm:
            raw = self.llm.complete(
                "You are a career coach. Suggest up to 3 resume bullet rewrites that better match the job. "
                "Only use experience present in the resume. Reply as JSON list of "
                '{"skill": str, "text": str}.',
                f"JOB:\n{state.job}\n\nRESUME:\n{state.resume}")
            for item in json.loads(raw):
                state.suggestions.append(Suggestion("reframe", item["skill"], item["text"]))


# ------------------------------------------------------------------- reviewer
class ReviewerAgent(Agent):
    """Guardrail: drop any 'reframe' suggestion for a skill the resume never evidences."""
    name = "reviewer"

    def run(self, state: MatchState) -> None:
        kept = []
        for s in state.suggestions:
            if s.kind == "reframe" and s.skill not in state.candidate_skills:
                state.rejected.append(s)
            else:
                kept.append(s)
        state.suggestions = kept
