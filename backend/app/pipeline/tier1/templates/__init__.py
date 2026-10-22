"""The document templates, as data: one JSON file per layout, and its image.

A template says where a document type prints its fields, as a rectangle per
field in the reference image's own pixels and, since 13.8, how far each field
may sit from where that rectangle puts it.  No coordinate is written in Python
beside its file, and :mod:`app.pipeline.tier1.templates.loader` is the one way
in, so a caller holding a template holds a
:class:`~app.pipeline.tier1.templates.loader.Template` and never a path.

**The directory is a package because the files have to travel with the code.**
A layout the loader cannot find is a template with no fields on it, so the read
is a package-resource read -- :mod:`app.risk.weightsets` under `D15` is the
precedent -- and a missing file raises rather than answering with an empty one.

**The MRZ is not in a template.**  Tier 0 locates the zone by detecting it
(:func:`app.pipeline.tier0.mrz_region.detect_mrz`), so a rectangle naming the
zone here would be a second answer to a question one module already answers.
"""
