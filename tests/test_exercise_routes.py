"""TC-026, TC-027, TC-028 and TC-034: exercise route behavior."""

from unittest.mock import Mock


def test_tc026_exercise_history_not_answered(
    client, auth_headers, app_module, student_id, monkeypatch
):
    get_history = Mock(return_value=(2, None))
    monkeypatch.setattr(app_module, "get_exercise_history_db", get_history)

    response = client.post(
        "/api/student/getExerciseHistory",
        data={"exercise_id": "21"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.get_json() == {"ret": 2, "msg": "习题未作答！"}
    get_history.assert_called_once_with(student_id, "21")


def test_tc027_exercise_history_answered_but_not_checked(
    client, auth_headers, app_module, student_id, monkeypatch
):
    history = ("学生答案", "2026-09-14 10:30:00", None, None)
    get_history = Mock(return_value=(3, history))
    monkeypatch.setattr(app_module, "get_exercise_history_db", get_history)

    response = client.post(
        "/api/student/getExerciseHistory",
        data={"exercise_id": "22"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.get_json() == {
        "ret": 3,
        "msg": "习题未批改！",
        "student_answer": "学生答案",
        "answer_time": "2026-09-14 10:30:00",
        "check": None,
        "analyse": None,
    }
    get_history.assert_called_once_with(student_id, "22")


def test_tc028_exercise_history_checked(
    client, auth_headers, app_module, student_id, monkeypatch
):
    history = ("正确答案", "2026-09-14 11:00:00", 0, "回答正确")
    get_history = Mock(return_value=(0, history))
    monkeypatch.setattr(app_module, "get_exercise_history_db", get_history)

    response = client.post(
        "/api/student/getExerciseHistory",
        data={"exercise_id": "23"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.get_json() == {
        "ret": 0,
        "msg": "作答历史获取成功！",
        "student_answer": "正确答案",
        "answer_time": "2026-09-14 11:00:00",
        "check": 0,
        "analyse": "回答正确",
    }
    get_history.assert_called_once_with(student_id, "23")


def test_tc034_commit_exercise_with_non_numeric_id_returns_500(
    client, auth_headers, app_module, monkeypatch
):
    commit_exercise = Mock()
    monkeypatch.setattr(app_module, "commit_exercise_db", commit_exercise)

    response = client.post(
        "/api/student/commitExercise",
        data={"exercise_id": "not-a-number", "student_answer": "answer"},
        headers=auth_headers,
    )

    # This characterizes the current defect: invalid input is not handled as 4xx.
    assert response.status_code == 500
    commit_exercise.assert_not_called()
