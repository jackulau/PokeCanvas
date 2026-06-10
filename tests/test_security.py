import pytest

from src.canvas_client import CanvasError, resolve_canvas_credentials
from src.security import assert_safe_canvas_url


def test_allows_public_https_canvas():
    assert_safe_canvas_url("https://canvas.university.edu")  # must not raise
    assert_safe_canvas_url("https://canvas.test")


@pytest.mark.parametrize(
    "url",
    [
        "http://canvas.university.edu",  # non-https
        "https://127.0.0.1",  # loopback
        "https://10.0.0.5",  # RFC1918 private
        "https://192.168.1.10",  # RFC1918 private
        "https://172.16.5.5",  # RFC1918 private
        "https://169.254.169.254",  # link-local (cloud metadata)
        "https://[::1]",  # ipv6 loopback
        "https://metadata.google.internal",  # GCP metadata hostname
    ],
)
def test_blocks_unsafe_targets(url):
    with pytest.raises(CanvasError):
        assert_safe_canvas_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "https://2130706433",  # decimal 127.0.0.1
        "https://0x7f000001",  # hex 127.0.0.1
        "https://0177.0.0.1",  # dotted-octal 127.0.0.1
        "https://0x7f.0.0.1",  # mixed-base
        "https://127.1",  # short form -> 127.0.0.1
        "https://2852039166",  # decimal 169.254.169.254 (metadata)
        "https://[::ffff:127.0.0.1]",  # IPv4-mapped IPv6 loopback
        "https://[fd00::1]",  # IPv6 unique-local
    ],
)
def test_blocks_encoded_ip_bypasses(url):
    with pytest.raises(CanvasError):
        assert_safe_canvas_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "https://canvas.university.edu",
        "https://canvas.test",
        "https://canvas.instructure.com",
        "https://my-canvas.school.edu",
    ],
)
def test_allows_legit_canvas_hosts(url):
    assert_safe_canvas_url(url)  # must not raise


def test_resolve_blocks_ssrf_via_composite():
    with pytest.raises(CanvasError) as exc:
        resolve_canvas_credentials(auth_header="Bearer https://169.254.169.254::tok", env={})
    assert exc.value.status == 400


def test_resolve_blocks_private_ip_base_header():
    with pytest.raises(CanvasError):
        resolve_canvas_credentials(base_url_header="https://10.1.2.3", env={"CANVAS_API_TOKEN": "t"})


def test_resolve_allows_normal_composite():
    base, token = resolve_canvas_credentials(auth_header="Bearer https://canvas.uni.edu::tok", env={})
    assert base == "https://canvas.uni.edu"
    assert token == "tok"
