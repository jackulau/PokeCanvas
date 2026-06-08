from src.ratelimit import RateLimiter
from src.tools import _rate_key


class FakeClock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


class FakeRequest:
    """Duck-types starlette's case-insensitive request.headers.get."""

    def __init__(self, headers: dict):
        self._h = {k.lower(): v for k, v in headers.items()}

    @property
    def headers(self):
        return self._h


def test_allows_up_to_limit():
    rl = RateLimiter(max_requests=3, window_seconds=60, clock=lambda: 0)
    assert [rl.allow("u") for _ in range(3)] == [True, True, True]


def test_blocks_over_limit():
    rl = RateLimiter(max_requests=3, window_seconds=60, clock=lambda: 0)
    for _ in range(3):
        rl.allow("u")
    assert rl.allow("u") is False


def test_window_slides():
    clock = FakeClock()
    rl = RateLimiter(max_requests=2, window_seconds=60, clock=clock)
    assert rl.allow("u") and rl.allow("u")
    assert rl.allow("u") is False
    clock.t = 61  # old hits fall out of the window
    assert rl.allow("u") is True


def test_keys_are_isolated():
    rl = RateLimiter(max_requests=1, window_seconds=60, clock=lambda: 0)
    assert rl.allow("a") is True
    assert rl.allow("b") is True
    assert rl.allow("a") is False


def test_rate_key_prefers_poke_user_id():
    assert _rate_key(FakeRequest({"X-Poke-User-Id": "abc-123"})) == "user:abc-123"


def test_rate_key_hashes_token_without_user_id():
    key = _rate_key(FakeRequest({"Authorization": "Bearer super-secret-token"}))
    assert key.startswith("tok:")
    assert "super-secret-token" not in key
