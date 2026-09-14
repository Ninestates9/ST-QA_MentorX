from unittest.mock import Mock

from werkzeug.security import generate_password_hash

import main


def test_tc001_login_phone_not_found(client, monkeypatch):
    sign_in = Mock(return_value=None)
    monkeypatch.setattr(main, "sign_in_db", sign_in)

    response = client.post(
        "/api/signIn",
        data={"phone_number": "13800000000", "password": "anything"},
    )

    assert response.status_code == 200
    assert response.get_json() == {"ret": 1, "msg": "手机号不存在！"}
    assert "jwt" not in response.get_json()
    sign_in.assert_called_once_with("13800000000")


def test_tc003_login_success_returns_user_and_jwt(client, monkeypatch):
    sign_in = Mock(
        return_value=(generate_password_hash("right-password"), 7, "student", "小明", "男")
    )
    monkeypatch.setattr(main, "sign_in_db", sign_in)

    response = client.post(
        "/api/signIn",
        data={"phone_number": "13800000001", "password": "right-password"},
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["ret"] == 0
    assert payload["name"] == "小明"
    assert payload["gender"] == "男"
    assert payload["type"] == "student"
    assert isinstance(payload["jwt"], str) and payload["jwt"]
    sign_in.assert_called_once_with("13800000001")


def test_tc006_register_success_forwards_all_fields(client, monkeypatch):
    register = Mock(return_value=True)
    monkeypatch.setattr(main, "register_db", register)
    form = {
        "phone_number": "13900000000",
        "password": "pw",
        "type": "teacher",
        "name": "王老师",
        "gender": "女",
    }

    response = client.post("/api/register", data=form)

    assert response.status_code == 200
    assert response.get_json() == {
        "ret": 0,
        "msg": "用户13900000000注册成功！",
    }
    register.assert_called_once_with("13900000000", "pw", "teacher", "王老师", "女")


def test_tc007_update_info_without_jwt_does_not_call_db(client, monkeypatch):
    update = Mock()
    monkeypatch.setattr(main, "update_info_db", update)

    response = client.post("/api/updateInfo", data={"name": "新名字"})

    assert response.status_code == 401
    update.assert_not_called()


def test_tc008_update_info_uses_jwt_identity(client, auth_headers, monkeypatch):
    update = Mock(return_value=True)
    monkeypatch.setattr(main, "update_info_db", update)

    response = client.post(
        "/api/updateInfo",
        data={"password": "new-pw", "name": "新名字", "gender": "女"},
        headers=auth_headers(42),
    )

    assert response.status_code == 200
    assert response.get_json() == {"ret": 0, "msg": "用户42信息修改成功！"}
    update.assert_called_once_with(42, "new-pw", "新名字", "女")

