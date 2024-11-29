import pytest
from datetime import datetime
from coeur.apps.cmp.engine import Engine
from unittest.mock import MagicMock


def today():
    return datetime.now().strftime("%Y/%m/%d")


@pytest.mark.parametrize(
    "custom_path, content_title, expected_result",
    [
        ("/Test Path//Example/", "Test Title", "/test-path/example/"),
        ("", "Test Title", f"/{today()}/test-title/"),
        (
            "/Special-Characters!/Path/",
            "Special Path!",
            "/special-characters/path/",
        ),
        ("/no-slug-needed/", "Simple Title", "/no-slug-needed/"),
        (
            "another-Test///With//Extra//slashes",
            "Extra Slashes",
            "/another-test/with/extra/slashes/",
        ),
    ],
)
def test_build_post_path(custom_path, content_title, expected_result):
    content = MagicMock()
    content.title = content_title
    result = Engine.build_post_path(content, custom_path)
    assert result == expected_result
