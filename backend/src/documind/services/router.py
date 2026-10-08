"""A small rule router keeps ordinary document questions on the cheaper RAG path."""

import re


def requests_ticket(question: str) -> bool:
    return bool(
        re.search(
            r"\b(create|open|raise|file|submit|draft)\b.{0,60}\b(ticket|support request)\b",
            question,
            re.IGNORECASE,
        )
    )


def needs_tools(question: str) -> bool:
    """doc-mind-ai: route explicit order checks or ticket actions, not policy keywords."""
    order = re.search(r"\bORD-\d+\b", question, re.IGNORECASE) and re.search(
        r"\b(status|track|where|delivery|shipped|arrive)\b", question, re.IGNORECASE
    )
    return bool(requests_ticket(question) or order)
