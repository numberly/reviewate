"""Agents Module — Claude Agent SDK based agents for code review."""

from code_reviewer.agents.analyzer import AnalyzeAgent
from code_reviewer.agents.base import AgentResult, BaseAgent
from code_reviewer.agents.deduplicator import DedupAgent
from code_reviewer.agents.fact_checker import FactCheckAgent
from code_reviewer.agents.issue_explorer import IssueExplorerAgent
from code_reviewer.agents.post_fixer import PostingFixAgent
from code_reviewer.agents.styler import StyleAgent
from code_reviewer.agents.summary import SummarizerAgent
from code_reviewer.agents.summary_parser import SummaryParserAgent
from code_reviewer.agents.synthesizer import SynthesizerAgent

__all__ = [
    "AgentResult",
    "AnalyzeAgent",
    "BaseAgent",
    "DedupAgent",
    "FactCheckAgent",
    "IssueExplorerAgent",
    "PostingFixAgent",
    "StyleAgent",
    "SummarizerAgent",
    "SummaryParserAgent",
    "SynthesizerAgent",
]
