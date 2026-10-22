"""What every test in this suite is handed before it runs.

Two things.  **The rate limiter 11.8 added** counts per address, and the test
client has one address, so a limiter left counting from an earlier test would
refuse the first requests of a later one and turn an unrelated failure into a
429.  Each test therefore starts against a freshly built limiter at the limit
the app was configured with, and the shipped one is put back afterwards, so a
test that swaps in its own leaves nothing behind.

**The evidence store 19.6 added** is a directory of encrypted blobs, and a
suite that reached the shipped one would write every upload it posts into the
repository -- which is the one thing this suite must not do, and is why
``test_alembic_migration.py`` checks that no ``drishti.db`` is left beside the
code.  Every test is therefore handed a store over a temporary directory, and
a test that wants one of its own overrides this the way it overrides the
limiter.
"""

import pytest

from app.api import get_evidence_store
from app.api.rate_limit import RateLimiter
from app.config import ENV_DEVELOPMENT
from app.main import app
from app.storage.blob_store import EvidenceStore
from app.storage.master_key import load_master_key


@pytest.fixture(autouse=True)
def rate_limiter_is_empty():
    """Hand this test an empty limiter, and leave the app as it was found."""
    shipped = app.state.rate_limiter
    app.state.rate_limiter = RateLimiter(shipped.limit)
    try:
        yield
    finally:
        app.state.rate_limiter = shipped


@pytest.fixture(autouse=True)
def evidence_store_is_temporary(tmp_path_factory):
    """Hand this test a store over a temporary directory, and nothing else.

    The key is a generated development one, so nothing this suite writes is
    readable afterwards by anything -- the same reason D154 generates rather
    than ships one -- and no test depends on whatever
    ``EVIDENCE_ENCRYPTION_KEY`` the shell happens to hold.  The shipped
    override, if there was one, is put back rather than dropped, so a test
    that swapped in its own leaves nothing behind either.
    """
    store = EvidenceStore(
        tmp_path_factory.mktemp("evidence"), load_master_key(None, ENV_DEVELOPMENT)
    )
    shipped = app.dependency_overrides.get(get_evidence_store)
    app.dependency_overrides[get_evidence_store] = lambda: store
    try:
        yield store
    finally:
        if shipped is None:
            app.dependency_overrides.pop(get_evidence_store, None)
        else:
            app.dependency_overrides[get_evidence_store] = shipped
