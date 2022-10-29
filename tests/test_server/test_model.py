import pytest

from hface.server import Endpoint


class TestEndpoint:
    @pytest.mark.parametrize(
        "value, scheme, host, port",
        [
            (":8080", "http", "", 8080),
            ("//:8080", "http", "", 8080),
            ("http://:8080", "http", "", 8080),
            ("https://:8443", "https", "", 8443),
            ("example.com:8080", "http", "example.com", 8080),
            ("//example.com:8080", "http", "example.com", 8080),
            ("http://example.com:8080", "http", "example.com", 8080),
            ("https://example.com:8443", "https", "example.com", 8443),
            ("0.0.0.0:8080", "http", "0.0.0.0", 8080),
            ("[::]:8080", "http", "::", 8080),
            ("https://0.0.0.0:8443", "https", "0.0.0.0", 8443),
            ("https://[::]:8443", "https", "::", 8443),
        ],
    )
    def test_parse(self, value: str, scheme: str, host: str, port: int) -> None:
        assert Endpoint.parse(value) == Endpoint(scheme, host, port)

    @pytest.mark.parametrize(
        "value",
        [
            "//",
            "http://",
            "example.com",
            "//example.com",
            "http://example.com",
            "example.com:8080/foo",
            "example.com:8080?bar",
        ],
    )
    def test_parse_invalid(self, value: str) -> None:
        with pytest.raises(ValueError):
            Endpoint.parse(value)
