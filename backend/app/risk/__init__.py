"""Structured findings, and the risk decision they aggregate into.

A *flag* is one finding a screening can explain: what was checked, what was
found, where on the document it is, and which module produced it.  The record
is :class:`app.risk.flags.EvidenceFlag`, and it is the one type every tier
emits, whatever produced it.
"""
