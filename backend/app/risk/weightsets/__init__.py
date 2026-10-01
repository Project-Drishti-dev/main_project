"""The weightsets, as data: one file per version, and no numbers in Python.

``v1.yaml`` is the file 7.1 wrote and 7.1's tests hold complete, and this
package is what makes it reachable: :mod:`app.risk.weightsets.loader` reads it
through :func:`importlib.resources.files` rather than a path assembled out of
``__file__``, the way :mod:`app.seed` reads the watchlist seed (``D15``).

**The directory is a package because the file has to travel with the code.**
A weightset the engine cannot find is an engine that scores every flag at
zero, so the read is a package-resource read and a missing file raises rather
than answering.

``loader.py`` is the one way in and ``lookup.py`` is the one way out:
``weight_for(weightset, flag_id)`` answers from the record the loader handed
back, and raises ``WeightsetError`` for an id that record carries no usable
weight for, so a finding with no weight is never scored as worth nothing.
"""
