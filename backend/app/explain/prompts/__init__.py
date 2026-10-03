"""The versioned question a summary is asked, kept as data beside the code that asks it.

``v1.txt`` is prose rather than logic, so it is a file rather than a string in
Python: it carries the version it was written under in its own header, and
:mod:`app.explain.prompts.loader` is the one way in.  This package re-exports
nothing, as :mod:`app.explain` does.
"""
