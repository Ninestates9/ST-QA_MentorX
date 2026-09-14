from unittest.mock import Mock


def test_generate_ppt_01(client, app_module, monkeypatch):
    generate_ppt = Mock(return_value=(False, None, None, "章节不存在"))
    increase_count = Mock()
    monkeypatch.setattr(app_module, "ai_generate_ppt", generate_ppt)
    monkeypatch.setattr(app_module, "increase_count", increase_count)

    response = client.post("/api/generatePPT", data={"chapter_id": "404"})

    assert response.status_code == 200
    assert response.get_json() == {"ret": 1, "msg": "章节不存在"}
    generate_ppt.assert_called_once_with("404")
    increase_count.assert_not_called()
