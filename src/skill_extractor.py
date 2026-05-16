"""Extract functional / soft skills from job descriptions via regex.

Different from tech: these are role-shaped capabilities and experience signals
("distributed systems", "leadership", "research publications") rather than
named tools.
"""
from __future__ import annotations

import re
from collections import Counter

# Canonical skill -> list of regex alternations matched case-insensitively.
# Use word boundaries so we don't match inside other words.
SKILL_PATTERNS: dict[str, list[str]] = {
    # Engineering capability
    "Distributed Systems":       [r"distributed systems?"],
    "Systems Programming":       [r"systems programming", r"low[- ]level programming"],
    "Performance Optimization":  [r"performance (?:engineering|optimization|tuning)", r"profiling and optimization"],
    "Scalability":               [r"scalab(?:ility|le systems?)", r"high[- ]scale", r"large[- ]scale systems?"],
    "API Design":                [r"api design", r"designing apis?"],
    "Backend Development":       [r"backend (?:engineering|development)", r"server[- ]side"],
    "Frontend Development":      [r"frontend (?:engineering|development)", r"client[- ]side"],
    "Full-Stack":                [r"full[- ]stack"],
    "Mobile Development":        [r"mobile (?:engineering|development)", r"ios development", r"android development"],

    # ML / Research
    "Machine Learning":          [r"machine learning", r"\bml engineering\b", r"\bdeep learning\b"],
    "LLM Experience":            [r"\bllms?\b", r"large language models?", r"foundation models?"],
    "Pretraining":               [r"\bpre[- ]?training\b"],
    "Post-Training / RLHF":      [r"post[- ]training", r"\brlhf\b", r"\brlaif\b", r"reinforcement learning from human"],
    "Reinforcement Learning":    [r"reinforcement learning"],
    "Model Evaluation":          [r"model eval(?:uation)?s?\b", r"\bevals?\b "],
    "Inference Optimization":    [r"inference (?:optimization|performance|engine|serving)"],
    "ML Systems":                [r"\bml systems?\b", r"ml infrastructure", r"training infrastructure"],
    "Research Publications":     [r"published (?:research|papers?)", r"first[- ]author", r"top[- ]tier (?:conference|venue)", r"\bneurips\b", r"\bicml\b", r"\biclr\b"],
    "Interpretability":          [r"interpretability", r"mechanistic interp"],
    "Alignment":                 [r"\bai alignment\b", r"alignment research"],
    "AI Safety":                 [r"ai safety", r"safety research"],
    "Red Teaming":               [r"red[- ]team(?:ing)?"],

    # Infra / DevOps
    "Cloud Infrastructure":      [r"cloud (?:infrastructure|engineering|platform)"],
    "Site Reliability":          [r"\bsre\b", r"site reliability"],
    "Observability":             [r"observability", r"monitoring and alerting"],
    "Incident Response":         [r"incident response", r"on[- ]call"],
    "Networking":                [r"\bnetworking\b", r"network engineering"],
    "Linux Systems":             [r"linux (?:systems?|kernel|administration)"],
    "Hardware":                  [r"\bhardware\b engineering", r"\basic\b", r"\bfpga\b", r"silicon"],

    # Security
    "Security Engineering":      [r"security engineering", r"product security", r"application security"],
    "Cryptography":              [r"cryptograph(?:y|ic)"],
    "Threat Modeling":           [r"threat model(?:ing)?"],
    "Compliance":                [r"\bsoc ?2\b", r"\biso 27001\b", r"\bfedramp\b", r"\bgdpr\b", r"\bhipaa\b", r"compliance"],

    # Data
    "Data Engineering":          [r"data engineering", r"data pipelines?"],
    "Data Modeling":             [r"data modeling", r"schema design"],
    "Analytics":                 [r"\banalytics\b", r"\bbi\b ", r"business intelligence"],

    # Leadership / collaboration
    "Technical Leadership":      [r"technical lead(?:ership)?", r"\btech lead\b", r"\beng(?:ineering)? lead\b"],
    "People Management":         [r"people management", r"managing (?:engineers|a team)", r"direct reports"],
    "Mentorship":                [r"\bmentor(?:ing|ship)\b", r"coaching engineers?"],
    "Cross-Functional Collab":   [r"cross[- ]functional"],
    "Stakeholder Management":    [r"stakeholder (?:management|engagement)"],
    "Project Management":        [r"project management", r"program management"],

    # Soft skills (used judiciously — only strong, unambiguous signals)
    "Strong Communication":      [r"(?:strong|excellent) (?:written and verbal )?communication"],
    "Written Communication":     [r"strong writing skills", r"clear writer", r"technical writing"],
    "Customer-Facing":            [r"customer[- ]facing", r"client[- ]facing"],
    "Ambiguity Tolerance":       [r"thrive in ambiguity", r"comfortable with ambiguity", r"navigate ambiguity"],
    "Ownership":                 [r"sense of ownership", r"strong ownership", r"\bend[- ]to[- ]end ownership\b"],
    "Bias for Action":           [r"bias (?:for|toward) action"],

    # Experience signals
    "PhD-Level Research":        [r"\bphd\b(?:.{0,60})?(?:research|machine learning|computer science|physics|mathematics)"],
    "Startup Experience":        [r"startup (?:experience|environment)", r"early[- ]stage"],
    "Open Source":               [r"open[- ]source contributions?", r"contributed to open[- ]source"],
}


def _compile() -> dict[str, list[re.Pattern]]:
    return {
        skill: [re.compile(p, re.IGNORECASE) for p in pats]
        for skill, pats in SKILL_PATTERNS.items()
    }


_COMPILED = _compile()

# Boilerplate ("About Anthropic", "Compensation", "Logistics", etc.) appears in
# every JD and mentions things like "interpretable AI systems", "safe and
# beneficial", "diversity" — which would inflate every signal to ~100% recall.
# Strip everything before "About the Role" (or equivalent) and after sections
# like "Compensation", "Logistics", "How we're different", etc.
_BOILERPLATE_START = re.compile(
    r"(?is)\babout\s+(?:the\s+)?role\b|\babout\s+the\s+team\b|\bthe\s+role\b|"
    r"\bresponsibilities\b|\bwhat\s+you[''']ll\s+do\b",
)
_BOILERPLATE_END = re.compile(
    r"(?is)\bcompensation\b|\blogistics\b|\bhow\s+we[''']re\s+different\b|"
    r"\bcome\s+work\s+with\s+us\b|\bbenefits\b|\bannual\s+salary\b|"
    r"\bdeadline\s+to\s+apply\b|\beducation\s+requirements\b",
)


def _strip_boilerplate(text: str) -> str:
    """Trim the standard 'About Anthropic' intro and end-of-JD blocks so
    that boilerplate language doesn't drive every job's skill match."""
    if not text:
        return ""
    m = _BOILERPLATE_START.search(text)
    if m:
        text = text[m.start():]
    m = _BOILERPLATE_END.search(text)
    if m:
        text = text[:m.start()]
    return text


def extract_skills(text: str) -> list[str]:
    body = _strip_boilerplate(text)
    found = []
    for skill, patterns in _COMPILED.items():
        if any(p.search(body) for p in patterns):
            found.append(skill)
    return found


def annotate(jobs: list[dict]) -> list[dict]:
    """Add a 'skills' list to each job dict (in place)."""
    for j in jobs:
        j["skills"] = extract_skills(j.get("description", ""))
    return jobs


def top_skills(jobs: list[dict], n: int = 15) -> list[tuple[str, int]]:
    c: Counter[str] = Counter()
    for j in jobs:
        c.update(j.get("skills", []))
    return c.most_common(n)
