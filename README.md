# Job Match Agents

**A small multi-agent system that scores a resume against a job description, explains the gaps, and refuses to invent experience.**

Four agents share one state object and run in sequence. Each one can work with plain rules, so it's free, fast and deterministic, or with any OpenAI-compatible LLM. The last agent is a **guardrail**: it blocks any suggestion that would claim a skill the resume gives no evidence for.

```
 resume.md + job.txt
        │
        ▼
 ┌────────────┐   ┌───────────┐   ┌──────────┐   ┌─────────────────────────┐
 │ Extractor  │──►│  Matcher  │──►│  Coach   │──►│ Reviewer (guardrail)    │
 │ skills,    │   │ weighted  │   │ evidence │   │ drops suggestions for   │
 │ req vs     │   │ score,    │   │ gaps,    │   │ skills with no evidence │
 │ preferred, │   │ gaps      │   │ rewrites │   │ in the resume           │
 │ years      │   │           │   │          │   │                         │
 └────────────┘   └───────────┘   └──────────┘   └─────────────────────────┘
        ▼
 Markdown report: score breakdown, matched skills with evidence lines, gaps,
 suggestions, blocked suggestions, agent trace
```

## Design choices

- **Evidence, not keywords.** Each matched skill links to the resume line that proves it. A skill that only appears in a skills list gets flagged so you can back it up with a real bullet.
- **Separate required and preferred skills.** The job description is split into required and nice-to-have sections. The score is 70% required skills, 20% preferred skills and 10% experience.
- **A guardrail that doesn't trust the model it checks.** The Reviewer always runs on rules. If the LLM coach suggests "Shipped three MCP servers" and MCP isn't in the resume, the suggestion is blocked and listed separately.
- **Structured LLM output with validation.** The LLM extractor must return JSON drawn from a fixed skill taxonomy, and unknown skills are dropped.
- **No framework lock-in.** The orchestration is about 30 lines of plain Python, so the agent pattern is easy to see. The same design maps onto CrewAI or LangGraph.

## Quick start

```bash
git clone https://github.com/<you>/job-match-agents && cd job-match-agents
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

job-match --resume examples/resume.md --job examples/job.txt
pytest -q     # 8 passed
```

Sample output (rules mode):

```
Match score: 77.2/100
| required skills | 89% |   | preferred skills | 25% |   | experience | 100% |

Gaps
- AI Agents (required)
- LLM Evaluation (preferred)
- MCP (preferred)
...
```

With an LLM for extraction and bullet rewrites:

```bash
export OPENAI_API_KEY=...                          # any OpenAI-compatible endpoint
export OPENAI_BASE_URL=http://localhost:11434/v1   # optional: local Ollama
job-match --resume my_resume.md --job posting.txt --llm --out report.md
```

## Project layout

```
job_match/
  skills.py    # skill taxonomy + alias matching with evidence lines
  agents.py    # Extractor, Matcher, Coach, Reviewer + shared MatchState
  pipeline.py  # orchestrator + Markdown report
  llm.py       # dependency-free OpenAI-compatible client + scripted test client
  cli.py
examples/      # sample resume and job description (fictional)
tests/
```

## Roadmap

- PDF and DOCX resume parsing
- Embedding-based skill matching for phrasings the taxonomy doesn't cover
- Batch mode that ranks one resume against many postings

## License

MIT
