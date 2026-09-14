from unittest.mock import Mock

import aiPPT_http_utils as http_utils

from tests.fakes import FakeResponse


def test_post_sse_01(monkeypatch):
    response = FakeResponse(
        lines=[
            "event: message",
            'data: {"value": 1}',
            "data:",
            "data: [DONE]",
            'data:{"value": 2}',
        ]
    )
    post = Mock(return_value=response)
    monkeypatch.setattr(http_utils.requests, "post", post)
    items = []

    returned = http_utils.post_sse(
        "https://invalid.test/sse", {}, "{}", items.append, to_json=True
    )

    assert returned is response
    assert items == [{"value": 1}, {"value": 2}]
    assert post.call_args.kwargs["stream"] is True
    assert post.call_args.kwargs["verify"] is False

