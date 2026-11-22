"""Skill taxonomy: canonical names and the aliases people actually write."""

from __future__ import annotations

import re

TAXONOMY: dict[str, list[str]] = {
    "Python": ["python"],
    "SQL": ["sql", "t-sql", "postgresql", "postgres", "mysql", "sqlite"],
    "TypeScript": ["typescript"],
    "React": ["react", "react.js", "reactjs"],
    "FastAPI": ["fastapi"],
    "REST APIs": ["rest", "rest api", "rest apis", "restful"],
    "Docker": ["docker", "containers", "containerized"],
    "Kubernetes": ["kubernetes", "k8s", "aks", "eks", "gke"],
    "AWS": ["aws", "amazon web services"],
    "Azure": ["azure"],
    "GCP": ["gcp", "google cloud"],
    "Databricks": ["databricks", "unity catalog"],
    "Spark": ["spark", "pyspark"],
    "Delta Lake": ["delta lake", "delta tables"],
    "Airflow": ["airflow"],
    "LLMs": ["llm", "llms", "large language model", "large language models", "gpt", "claude", "llama"],
    "RAG": ["rag", "retrieval-augmented generation", "retrieval augmented generation"],
    "LangChain": ["langchain", "langgraph"],
    "CrewAI": ["crewai"],
    "AI Agents": ["agent", "agents", "agentic", "multi-agent", "multi agent"],
    "MCP": ["mcp", "model context protocol"],
    "Prompt Engineering": ["prompt engineering", "prompting"],
    "Fine-tuning": ["fine-tuning", "fine tuning", "finetuning", "lora", "qlora", "peft"],
    "Vector Databases": ["vector database", "vector db", "pinecone", "weaviate", "faiss", "pgvector", "chroma"],
    "LLM Evaluation": ["evals", "evaluation", "llm-as-a-judge", "llm as a judge"],
    "MLOps": ["mlops", "mlflow"],
    "PyTorch": ["pytorch", "torch"],
    "CI/CD": ["ci/cd", "github actions", "jenkins"],
    "Security": ["owasp", "rbac", "security", "sql injection"],
    "Data Quality": ["data quality", "data validation", "great expectations"],
}

_PATTERNS = {
    skill: re.compile(r"(?<![\w-])(" + "|".join(re.escape(a) for a in sorted(aliases, key=len, reverse=True))
                      + r")(?![\w-])", re.IGNORECASE)
    for skill, aliases in TAXONOMY.items()
}


def find_skills(text: str) -> dict[str, list[str]]:
    """Map each canonical skill found in `text` to the lines that mention it (evidence)."""
    found: dict[str, list[str]] = {}
    for line in (ln.strip(" -•*\t") for ln in text.splitlines()):
        if not line:
            continue
        for skill, pattern in _PATTERNS.items():
            if pattern.search(line):
                found.setdefault(skill, []).append(line)
    return found
