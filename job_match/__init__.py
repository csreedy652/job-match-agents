"""job-match-agents: a small multi-agent system that compares a resume with a job description."""

from .pipeline import run_pipeline, to_markdown

__all__ = ["run_pipeline", "to_markdown"]
__version__ = "0.1.0"
