from unittest.mock import Mock

import pytest

import main


def test_tc010_empty_chapter_list(client, monkeypatch):
    get_chapters = Mock(return_value=[])
    monkeypatch.setattr(main, "get_chapter_list_db", get_chapters)

    response = client.post("/api/getChapterList", data={"id": "3"})

    assert response.status_code == 200
    assert response.get_json()["ret"] == 0
    assert response.get_json()["chapterList"] == []
    get_chapters.assert_called_once_with("3")


def test_tc012_course_list_preserves_multiple_dicts(client, monkeypatch):
    courses = [
        {"id": 1, "name": "软件测试"},
        {"id": 2, "name": "软件工程"},
    ]
    get_courses = Mock(return_value=courses)
    monkeypatch.setattr(main, "get_course_list_db", get_courses)

    response = client.get("/api/getCourseList")

    assert response.status_code == 200
    assert response.get_json()["courseList"] == courses
    get_courses.assert_called_once_with()


def test_tc013_student_courses_without_jwt_does_not_call_db(client, monkeypatch):
    get_courses = Mock()
    monkeypatch.setattr(main, "get_course_list_db", get_courses)

    response = client.get("/api/student/getCourseList")

    assert response.status_code == 401
    get_courses.assert_not_called()


def test_tc019_update_exercise_with_no_changes_skips_db(client, monkeypatch):
    update = Mock()
    monkeypatch.setattr(main, "update_exercise_db", update)

    response = client.post(
        "/api/teacher/updateExercise",
        data={"id": "9", "content": "", "answer": "", "difficulty": "", "type": ""},
    )

    assert response.status_code == 200
    assert response.get_json() == {"ret": 1, "msg": "无修改内容！"}
    update.assert_not_called()


@pytest.mark.parametrize(
    ("url", "function_name"),
    [
        ("/api/admin/deleteUser", "delete_user_db"),
        ("/api/deleteCourse", "delete_course_db"),
        ("/api/deleteChapter", "delete_chapter_db"),
        ("/api/deleteExercise", "delete_exercise_db"),
    ],
)
@pytest.mark.parametrize(
    ("db_result", "expected"),
    [
        (True, {"ret": 0}),
        (False, {"ret": 1, "msg": "删除失败"}),
    ],
)
def test_tc022_delete_routes_map_db_result(
    client, monkeypatch, url, function_name, db_result, expected
):
    delete = Mock(return_value=db_result)
    monkeypatch.setattr(main, function_name, delete)

    response = client.post(url, data={"id": "17"})

    assert response.status_code == 200
    assert response.get_json() == expected
    delete.assert_called_once_with("17")
