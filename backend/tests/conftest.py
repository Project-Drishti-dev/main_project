"""What every test in this suite is handed before it runs.

Today that is the rate limiter 11.8 added.  It counts per address and the
test client has one address, so a limiter left counting from an earlier test
would refuse the first requests of a later one and turn an unrelated failure
into a 429.  Each test therefore starts against a freshly built limiter at
the limit the app was configured with, and the shipped one is put back
afterwards, so a test that swaps in its own leaves nothing behind.
"""

import pytest

from app.api.rate_limit import RateLimiter
from app.main import app


@pytest.fixture(autouse=True)
def rate_limiter_is_empty():
    """Hand this test an empty limiter, and leave the app as it was found."""
    shipped = app.state.rate_limiter
    app.state.rate_limiter = RateLimiter(shipped.limit)
    try:
        yield
    finally:
        app.state.rate_limiter = shipped
