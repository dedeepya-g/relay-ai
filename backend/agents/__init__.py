"""The ADK layer.

Relay's intake pipeline is deliberately deterministic: classification and
deduplication are model judgments, and everything after them is rule
application over campus policy. That is what makes an outcome reproducible and
an escalation defensible.

The agent does not sit inside that pipeline. It runs after it, reads the state
the pipeline produced, and decides what follow-up the situation warrants -- a
question that has no fixed right answer and so is worth an agent's judgment.
"""
