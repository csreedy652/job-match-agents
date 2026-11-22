import json
from pathlib import Path

from job_match.agents import _resume_years, _split_job_sections
from job_match.cli import main
from job_match.llm import ScriptedClient
from job_match.pipeline import run_pipeline, to_markdown
from job_match.skills import find_skills

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
RESUME = (EXAMPLES / "resume.md").read_text()
JOB = (EXAMPLES / "job.txt").read_text()


def test_find_skills_uses_aliases_and_word_boundaries():
    found = find_skills("Deployed on k8s with Docker\nWrote PostgreSQL queries\nTypescriptish is not a word")
    assert {"Kubernetes", "Docker", "SQL"} <= set(found)
    assert "TypeScript" not in found
    assert found["Kubernetes"] == ["Deployed on k8s with Docker"]


def test_job_sections_split():
    req, pref = _split_job_sections("Intro\nRequirements:\n- Python\nNice to have:\n- MCP\n")
    assert "Python" in req and "MCP" in pref and "MCP" not in req


def test_resume_years_from_stated_and_ranges():
    assert _resume_years("I have 6+ years of experience") == 6
    assert _resume_years("Engineer (2020 - 2023)\nAnalyst (2018 - 2020)") == 5


def test_pipeline_rules_mode():
    state = run_pipeline(RESUME, JOB)
    assert "AI Agents" in state.gaps and "MCP" in state.gaps
    assert {"Python", "RAG", "Kubernetes"} <= set(state.matched)
    assert state.required_years == 4 and state.candidate_years >= 4
    assert 0 < state.score < 100
    assert any(s.kind == "add_evidence" and s.skill == "Airflow" for s in state.suggestions)
    assert [t.split(":")[0] for t in state.trace] == ["extractor", "matcher", "coach", "reviewer"]


def test_reviewer_blocks_fabricated_suggestions():
    llm = ScriptedClient([
        json.dumps({"required": ["Python", "LLMs", "AI Agents"], "preferred": ["MCP"]}),
        json.dumps([
            {"skill": "RAG", "text": "Built a RAG assistant over internal docs with LangChain."},
            {"skill": "MCP", "text": "Shipped three MCP servers to production."},  # not in resume
        ]),
    ])
    state = run_pipeline(RESUME, JOB, llm)
    reframes = [s for s in state.suggestions if s.kind == "reframe"]
    assert [s.skill for s in reframes] == ["RAG"]
    assert [s.skill for s in state.rejected] == ["MCP"]
    assert "Blocked by reviewer" in to_markdown(state)


def test_llm_extraction_ignores_unknown_skills():
    llm = ScriptedClient([json.dumps({"required": ["Python", "Telepathy"], "preferred": ["Python", "MCP"]}), "[]"])
    state = run_pipeline(RESUME, JOB, llm)
    assert state.required == ["Python"] and state.preferred == ["MCP"]


def test_perfect_match_scores_100():
    state = run_pipeline("5 years building Python services with Docker.", "Requirements:\n- 3+ years Python\n- Docker")
    assert state.score == 100.0 and state.gaps == []


def test_cli_writes_report(tmp_path):
    out = tmp_path / "report.md"
    assert main(["--resume", str(EXAMPLES / "resume.md"), "--job", str(EXAMPLES / "job.txt"), "--out", str(out)]) == 0
    assert out.read_text().startswith("# Job match report")
