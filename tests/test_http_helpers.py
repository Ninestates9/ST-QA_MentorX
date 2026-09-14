from unittest.mock import MagicMock

import aiPPT_http_utils as http_utils


class _Response:
    status_code = 200

    def iter_lines(self):
        return iter(
            [
                b"event: message",
                b'data: {"value": 1}',
                b"data:",
                b"data: [DONE]",
                b'data:{"value": 2}',
            ]
        )


def test_post_sse_01(monkeypatch):
    response = _Response()
    post = MagicMock(return_value=response)
    monkeypatch.setattr(http_utils.requests, "post", post)
    items = []

    returned = http_utils.post_sse(
        "https://invalid.test/sse", {}, "{}", items.append, to_json=True
    )

    assert returned is response
    assert items == [{"value": 1}, {"value": 2}]
    assert post.call_args.kwargs["stream"] is True
    assert post.call_args.kwargs["verify"] is False
