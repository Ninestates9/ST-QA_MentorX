import pymysql
from werkzeug.security import generate_password_hash
import redis
from datetime import date, datetime

# Redis连接
redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
redis_keys = ["AIchat", "generate_exercises", "check_exercises", "generate_teachcontent", "generate_tasks", "check", "generate_suggestion", "generate_ppt"]

def connectSQL(p_user = 'root', p_db = 'mentorx'):
    f_conn = pymysql.connect(
        host='127.0.0.1', 
        port=3306, 
        user=p_user, 
        password='123456', 
        charset='utf8mb4', 
        autocommit=True
    )
    f_cursor = f_conn.cursor()
    f_cursor.execute("use " + p_db)
    return f_conn, f_cursor

def closeSQL(p_conn, p_cursor):
    p_cursor.close()
    p_conn.close()

def init_redis_counters():
    conn, cursor = connectSQL()
    try:
        cursor.execute("SELECT * FROM system_stats;")
        row = cursor.fetchone()
        if row:
            for i, key in enumerate(redis_keys):
                redis_client.set(key, row[i])
    finally:
        closeSQL(conn, cursor)

def f_getLearningStatsByPerson(user_id, teacher_id = None):
    student = {}
    courses = []
    conn, cursor = connectSQL()

    sql = "SELECT name FROM user WHERE user_id = %s;"
    cursor.execute(sql, (user_id,))
    name = cursor.fetchone()[0]
    student["id"] = user_id
    student["name"] = name

    if teacher_id:
        sql = "SELECT course_id FROM course, course_student WHERE course.id = course_student.course_id AND student_id = %s AND teacher = %s;"
        cursor.execute(sql, (user_id, teacher_id))
        course_ids = cursor.fetchall()
    else:
        sql = "SELECT course_id FROM course_student WHERE student_id = %s;"
        cursor.execute(sql, (user_id))
        course_ids = cursor.fetchall()

    for course_id in course_ids:
        course = f_getLearningStatsByCourse(course_id, user_id)
        courses.append(course)
    
    student["courses"] = courses

    closeSQL(conn, cursor)
    return student

def f_getLearningStatsByChapter(chapter_id, student_id = None):
    conn, cursor = connectSQL()
    chapter = {}
    sql = "SELECT name FROM chapter WHERE id = %s;"
    cursor.execute(sql, (chapter_id,))
    chapter["name"] = cursor.fetchone()[0]
    
    if student_id:
        sql = "SELECT COUNT(*) FROM communicate_history WHERE chapter_id = %s AND student_id = %s;"
        cursor.execute(sql, (chapter_id, student_id))
        chapter["AiFrequence"] = cursor.fetchone()[0] / 2
        
        sql = "SELECT COUNT(*) FROM practice_history WHERE chapter_id = %s AND student_id = %s;"
        cursor.execute(sql, (chapter_id, student_id))
        total = cursor.fetchone()[0]
        
        sql = "SELECT COUNT(*) FROM practice_history WHERE chapter_id = %s AND `check` = '0' AND student_id = %s;"
        cursor.execute(sql, (chapter_id, student_id))
        right = cursor.fetchone()[0]
        
        chapter["correctness"] = right / total if total > 0 else 0
        chapter["sum_exercises"] = total 
        chapter["right_exercises"] = right
    else:
        sql = "SELECT COUNT(*) FROM communicate_history WHERE chapter_id = %s;"
        cursor.execute(sql, (chapter_id,))
        chapter["AiFrequence"] = cursor.fetchone()[0] / 2
        
        sql = "SELECT COUNT(*) FROM practice_history WHERE chapter_id = %s;"
        cursor.execute(sql, (chapter_id,))
        total = cursor.fetchone()[0]
        
        sql = "SELECT COUNT(*) FROM practice_history WHERE chapter_id = %s AND `check` = '0';"
        cursor.execute(sql, (chapter_id,))
        right = cursor.fetchone()[0]
        
        chapter["correctness"] = right / total if total > 0 else 0
        chapter["sum_exercises"] = total 
        chapter["right_exercises"] = right
    
    closeSQL(conn, cursor)
    return chapter

def f_getLearningStatsByCourse(course_id, student_id = None):
    conn, cursor = connectSQL()
    course = {}
    chapters = []

    sql = "SELECT name FROM course WHERE id = %s;"
    cursor.execute(sql, (course_id, ))
    name = cursor.fetchone()[0]

    course["id"] = course_id
    course["name"] = name 

    sql = "SELECT DISTINCT id FROM chapter WHERE course_id = %s;"
    cursor.execute(sql, (course_id))
    chapter_ids = cursor.fetchall()

    for chapter_id in chapter_ids:
        if student_id:
            chapter = f_getLearningStatsByChapter(chapter_id, student_id)
        else:
            chapter = f_getLearningStatsByChapter(chapter_id)
        chapters.append(chapter)

    course["chapters"] = chapters        
    closeSQL(conn, cursor)
    return course

def sign_in_db(phone_number):
    conn, cursor = connectSQL()
    try:       
        sql = "SELECT password, user_id, type, name, gender FROM user WHERE phone_number = %s;"
        cursor.execute(sql, (phone_number,))  
        info = cursor.fetchone() 
        return info
    finally:
        closeSQL(conn, cursor)

def increase_frequence(student_id):
    conn, cursor = connectSQL()
    try:
        sql = "UPDATE user SET frequence = frequence + 1 WHERE user_id = %s;"
        cursor.execute(sql, (student_id, ))
    finally:
        closeSQL(conn, cursor)

def register_db(phone_number, password, user_type, name, gender):
    conn, cursor = connectSQL()
    try:
        sql = "SELECT phone_number FROM user WHERE phone_number = %s;"
        cursor.execute(sql, (phone_number,))
        existing_user = cursor.fetchone()
        
        if existing_user:
            return False
        
        hashed_password = generate_password_hash(password)

        sql = "INSERT INTO user(phone_number, password, type, name, gender) VALUES(%s, %s, %s, %s, %s);"
        cursor.execute(sql, (phone_number, hashed_password, user_type, name, gender))
        return True
    finally:
        closeSQL(conn, cursor)

def update_info_db(user_id, password, name, gender):
    conn, cursor = connectSQL()
    try:
        sql = "SELECT type FROM user WHERE user_id = %s;"
        cursor.execute(sql, (user_id,))
        user_exists = cursor.fetchone()
        
        if not user_exists:
            return False
        
        if password:
            sql = "UPDATE user SET password = %s WHERE user_id = %s;"
            cursor.execute(sql, (password, user_id))
        if name:
            sql = "UPDATE user SET name = %s WHERE user_id = %s;"
            cursor.execute(sql, (name, user_id))
        if gender:
            sql = "UPDATE user SET gender = %s WHERE user_id = %s;"
            cursor.execute(sql, (gender, user_id))
        
        return True
    finally:
        closeSQL(conn, cursor)

def get_learning_stats_by_person_db(user_id, teacher_id = None):
    conn, cursor = connectSQL()
    try:
        if user_id:
            sql = "SELECT type FROM user WHERE user_id = %s;"
            cursor.execute(sql, (user_id,))
            result = cursor.fetchone()
            return [user_id] if result else None
        elif teacher_id:
            sql = "SELECT student_id FROM course, course_student WHERE course.id = course_student.course_id AND teacher = %s;"
            cursor.execute(sql, (teacher_id,))
            return [row[0] for row in cursor.fetchall()]
        else:
            sql = "SELECT user_id FROM user WHERE type = 'S';"
            cursor.execute(sql)
            return [row[0] for row in cursor.fetchall()]
    finally:
        closeSQL(conn, cursor)

def get_learning_stats_by_chapter_db(chapter_id):
    conn, cursor = connectSQL()
    try:
        if chapter_id:
            sql = "SELECT name FROM chapter WHERE id = %s;"
            cursor.execute(sql, (chapter_id,))
            result = cursor.fetchone()
            return [chapter_id] if result else None
        else:
            sql = "SELECT id FROM chapter;"
            cursor.execute(sql)
            return [row[0] for row in cursor.fetchall()]
    finally:
        closeSQL(conn, cursor)

def get_learning_stats_by_course_db(course_id, teacher_id = None):
    conn, cursor = connectSQL()
    try:
        if course_id:
            sql = "SELECT id FROM course WHERE id = %s;"
            cursor.execute(sql, (course_id,))
            result = cursor.fetchone()
            return [course_id] if result else None
        elif teacher_id:
            sql = "SELECT id FROM course WHERE teacher = %s;"
            cursor.execute(sql, (teacher_id,))
            return [row[0] for row in cursor.fetchall()]
        else:
            sql = "SELECT DISTINCT id FROM course;"
            cursor.execute(sql)
            return [row[0] for row in cursor.fetchall()]
    finally:
        closeSQL(conn, cursor)

def get_chapter_list_db(course_id):
    conn, cursor = connectSQL()
    try:
        sql = "SELECT id, name, content FROM chapter WHERE course_id = %s;"
        cursor.execute(sql, (course_id,))
        return cursor.fetchall()
    finally:
        closeSQL(conn, cursor)

def get_ai_list_db(course_id, student_id):
    conn, cursor = connectSQL()
    try:
        sql = "SELECT DISTINCT chapter.id, chapter.name FROM chapter, communicate_history WHERE course_id = %s AND student_id = %s AND chapter.id = communicate_history.chapter_id;"
        cursor.execute(sql, (course_id, student_id))
        return cursor.fetchall()
    finally:
        closeSQL(conn, cursor)

def get_ai_chat_db(student_id, chapter_id):
    conn, cursor = connectSQL()
    try:
        sql = "SELECT session_id, session_name, type, content, REPLACE(REPLACE(time, ' GMT', ''), 'UTC', '') AS time FROM communicate_history WHERE student_id = %s AND chapter_id = %s;"
        cursor.execute(sql, (student_id, chapter_id))
        return cursor.fetchall()
    finally:
        closeSQL(conn, cursor)

def get_course_list_db(student_id = None, teacher_id = None):
    conn, cursor = connectSQL()
    try:
        if student_id is None and teacher_id is None:
            sql = "SELECT DISTINCT id FROM course;"
            cursor.execute(sql)
        elif teacher_id is not None:
            sql = "SELECT DISTINCT id FROM course WHERE teacher = %s;"
            cursor.execute(sql, (teacher_id))
        elif student_id is not None:
            sql = "SELECT DISTINCT course_id FROM course_student WHERE student_id = %s;"
            cursor.execute(sql, (student_id))
        course_ids = [row[0] for row in cursor.fetchall()]
        
        courses = []
        for course_id in course_ids:
            sql = "SELECT name, teacher FROM course WHERE id = %s;"
            cursor.execute(sql, (course_id,))
            course_info = cursor.fetchone()
            
            sql = "SELECT name FROM user WHERE user_id = %s;"
            cursor.execute(sql, (course_info[1],))
            teacher_name = cursor.fetchone()[0]
            
            sql = "SELECT COUNT(*) FROM course_student WHERE course_id = %s;"
            cursor.execute(sql, (course_id,))
            student_count = cursor.fetchone()[0]
            
            if teacher_id is None:
                courses.append({
                    "id": course_id,
                    "name": course_info[0],
                    "teacher_id": course_info[1],
                    "teacher_name": teacher_name,
                    "student_num": student_count
                })
            else:
                courses.append({
                    "id": course_id,
                    "name": course_info[0],
                    "student_num": student_count
                })   
        return courses
    finally:
        closeSQL(conn, cursor)

def get_exercises_list_teacher_db(chapter_id):
    conn, cursor = connectSQL()
    try:
        sql = "SELECT id, exercise_content, answer, difficulty, type FROM exercise WHERE chapter_id = %s AND is_official = 1 AND is_daily = 0;"
        cursor.execute(sql, (chapter_id,))
        rows =  cursor.fetchall()

        new_rows = []
        for row in rows:
            sql = "SELECT COUNT(*) FROM practice_history WHERE exercise_id = %s;"
            cursor.execute(sql, (row[0],))
            count = cursor.fetchone()[0] or 0  
            new_rows.append( (*row, count) )   
        rows = new_rows  
        return rows
    finally:
        closeSQL(conn, cursor)

def get_exercises_list_student_db(student_id, chapter_id):
    conn, cursor = connectSQL()
    try:
        sql = "SELECT id, type, difficulty, exercise_content, is_official FROM exercise WHERE chapter_id = %s AND (is_official = 1 OR student_id = %s) AND is_daily = 0;"
        cursor.execute(sql, (chapter_id, student_id))
        rows =  cursor.fetchall()

        new_rows = []
        for row in rows:
            sql = "SELECT student_answer FROM practice_history WHERE exercise_id = %s AND student_id = %s;"
            cursor.execute(sql, (row[0], student_id))
            result = cursor.fetchone()
            new_rows.append( (*row, 1 if result else 0) )   
        rows = new_rows  
        return rows
    finally:
        closeSQL(conn, cursor)

def get_exercises_list_daily_db(student_id):
    conn, cursor = connectSQL()
    try:
        sql = "SELECT id, exercise_content, exercise_date FROM exercise WHERE is_daily = 1 AND student_id = %s;"
        cursor.execute(sql, (student_id))
        rows =  cursor.fetchall()

        new_rows = []
        for row in rows:
            sql = "SELECT student_answer, `check` FROM practice_history WHERE exercise_id = %s AND student_id = %s;"
            cursor.execute(sql, (row[0], student_id))
            result = cursor.fetchone()
            if result:
                new_rows.append( (row[0], row[1], format_date(row[2]), 1 if result[0] else 0, result[1]) ) 
            else:
                new_rows.append( (row[0], row[1], format_date(row[2]), 0, None) )  
        rows = new_rows  
        return rows
    finally:
        closeSQL(conn, cursor)

def join_course_db(course_id, student_id):
    conn, cursor = connectSQL()
    try:
        sql = "SELECT * FROM course WHERE id = %s;"
        cursor.execute(sql, (course_id,))
        result = cursor.fetchone()
        
        if result is None:
            return False
    
        sql = "INSERT INTO course_student values(%s, %s);"
        cursor.execute(sql, (course_id, student_id))   
        return True
    except:
        return False
    finally:
        closeSQL(conn, cursor)

def commit_exercise_db(student_id, exercise_id, student_answer):
    conn, cursor = connectSQL()
    try:
        sql = "SELECT `check` FROM practice_history WHERE student_id = %s AND exercise_id = %s;"
        cursor.execute(sql, (student_id, exercise_id))
        result = cursor.fetchone()
        if not result:
            sql = "SELECT chapter_id FROM exercise WHERE id = %s;"
            cursor.execute(sql, (exercise_id,))
            chapter_id = cursor.fetchone()[0]
            sql = "INSERT INTO practice_history(student_id, exercise_id, student_answer, chapter_id, time) values(%s, %s, %s, %s, CURRENT_TIMESTAMP);"
            cursor.execute(sql, (student_id, exercise_id, student_answer, chapter_id))
            return True
        elif result[0]:
            return False
        else:
            sql = "UPDATE practice_history SET student_answer = %s, time = CURRENT_TIMESTAMP WHERE student_id = %s AND exercise_id = %s;"
            cursor.execute(sql, (student_answer, student_id, exercise_id))
            return True
    finally:
        closeSQL(conn, cursor)

def add_course_db(name, teacher_id):
    conn, cursor = connectSQL()
    try:
        sql = "INSERT INTO course(name, teacher) VALUES(%s, %s);"
        cursor.execute(sql, (name, teacher_id))
        return True
    finally:
        closeSQL(conn, cursor)

def update_exercise_db(id, content, answer, difficulty, type):
    conn, cursor = connectSQL()
    try:
        if content:
            sql = "UPDATE exercise SET exercise_content = %s WHERE id = %s;"
            cursor.execute(sql, (content, id))
        if answer:
            sql = "UPDATE exercise SET answer = %s WHERE id = %s;"
            cursor.execute(sql, (answer, id))
        if difficulty:
            sql = "UPDATE exercise SET difficulty = %s WHERE id = %s;"
            cursor.execute(sql, (difficulty, id))
        if type:
            sql = "UPDATE exercise SET type = %s WHERE id = %s;"
            cursor.execute(sql, (type, id))
        
        return True
    finally:
        closeSQL(conn, cursor)

def update_chapter_db(id, content, name):
    conn, cursor = connectSQL()
    try:
        if content:
            sql = "UPDATE chapter SET content = %s WHERE id = %s;"
            cursor.execute(sql, (content, id))
        if name:
            sql = "UPDATE chapter SET name = %s WHERE id = %s;"
            cursor.execute(sql, (name, id))
        
        return True
    finally:
        closeSQL(conn, cursor)

def get_user_list_db(user_type):
    conn, cursor = connectSQL()
    try:
        sql = "SELECT user_id, phone_number, name, gender, frequence, sum_time FROM user WHERE type = %s;"
        cursor.execute(sql, (user_type,))
        return cursor.fetchall()
    finally:
        closeSQL(conn, cursor)

def delete_user_db(user_id):
    conn, cursor = connectSQL()
    try:
        sql = "DELETE FROM user WHERE user_id = %s;"
        cursor.execute(sql, (user_id,))
        return True
    finally:
        closeSQL(conn, cursor)

def get_system_stats_db():
    try:
        systemStats = [int(redis_client.get(key) or 0) for key in redis_keys]
        return systemStats
    except Exception as e:
        print("Redis获取系统统计失败，降级MySQL", e)
        conn, cursor = connectSQL()
        try:
            sql = "SELECT * FROM system_stats;"
            cursor.execute(sql)
            return cursor.fetchone()
        finally:
            closeSQL(conn, cursor)

def get_exercise_history_db(student_id, exercise_id):
    conn, cursor = connectSQL()
    try:
        sql = "SELECT student_answer, time, `check`, analyse FROM practice_history WHERE student_id = %s AND exercise_id = %s;"
        cursor.execute(sql, (student_id, exercise_id))
        result = cursor.fetchone()
        if not result:
            return 2, None
        if result[2] is None:
            return 3, result
        return 0, result
    finally:
        closeSQL(conn, cursor)

def get_student_exercises_db(exercise_id):
    conn, cursor = connectSQL()
    try:
        sql = "SELECT student_id, student_answer, time, `check`, analyse, user.name FROM practice_history, user WHERE exercise_id = %s AND practice_history.student_id = user.user_id;"
        cursor.execute(sql, (exercise_id,))
        return cursor.fetchall()
    finally:
        closeSQL(conn, cursor)

def delete_course_db(course_id):
    conn, cursor = connectSQL()
    try:
        sql = "DELETE FROM course WHERE id = %s;"
        cursor.execute(sql, (course_id,))
        return True
    finally:
        closeSQL(conn, cursor)

def delete_chapter_db(chapter_id):
    conn, cursor = connectSQL()
    try:
        sql = "DELETE FROM chapter WHERE id = %s;"
        cursor.execute(sql, (chapter_id,))
        return True
    finally:
        closeSQL(conn, cursor)

def delete_exercise_db(exercise_id):
    conn, cursor = connectSQL()
    try:
        sql = "DELETE FROM exercise WHERE id = %s;"
        cursor.execute(sql, (exercise_id,))
        return True
    finally:
        closeSQL(conn, cursor)

def increase_count(name):
    try:
        redis_client.incr(name)
        return True
    except Exception as e:
        print("Redis计数失败，降级MySQL", e)
        conn, cursor = connectSQL()
        try:
            sql = f"UPDATE system_stats SET `{name}` = `{name}` + 1;"
            cursor.execute(sql)
            return True
        finally:
            closeSQL(conn, cursor)

def sum_time_db(user_id, time):
    conn, cursor = connectSQL()
    try:
        sql = "UPDATE user SET sum_time = sum_time + %s WHERE user_id = %s;"
        cursor.execute(sql, (time, user_id))
        return True, "使用时长统计成功！"
    finally:
        closeSQL(conn, cursor)

def get_system_info_db():
    conn, cursor = connectSQL()
    systemInfo = {}
    tables = ["user", "course", "chapter"]
    try:
        cursor.execute("SELECT COUNT(*) FROM exercise WHERE is_official = 1;")
        systemInfo["exercise_num"] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM user WHERE gender = 'female';")
        systemInfo["female_num"] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM user WHERE gender = 'male';")
        systemInfo["male_num"] = cursor.fetchone()[0]

        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table};")
            systemInfo[table + "_num"] = cursor.fetchone()[0]

        return systemInfo
    finally:
        closeSQL(conn, cursor)
    

def search_worst_chapter(student_id):
    conn, cursor = connectSQL()
    try:
        sql = '''
        SELECT chapter_id, 
        SUM(CASE WHEN `check` = '0' THEN 1 ELSE 0 END) / COUNT(*) AS correctness
        FROM practice_history
        WHERE student_id = %s
        GROUP BY chapter_id
        ORDER BY correctness ASC;
        '''
        cursor.execute(sql, (student_id,))
        rows = cursor.fetchall()
        return rows[0][0]
    finally:
        closeSQL(conn, cursor)

def get_chapter_practice_history_db(student_id, chapter_id):
    conn, cursor = connectSQL()
    try:
        sql = '''
        SELECT exercise_content, student_answer, analyse, `check`
        FROM practice_history, exercise
        WHERE practice_history.student_id = %s AND practice_history.chapter_id = %s AND practice_history.exercise_id = exercise.id;
        '''
        cursor.execute(sql, (student_id, chapter_id))
        return cursor.fetchall()
    finally:
        closeSQL(conn, cursor)

def get_suggestion_db(chapter_id):
    conn, cursor = connectSQL()
    sql = "SELECT suggestion, suggestion_time FROM chapter WHERE id = %s;"
    cursor.execute(sql, (chapter_id,))
    result = cursor.fetchone()  
    closeSQL(conn, cursor)
    if result:
        result = (result[0], format_date(result[1]))
    return result if result else None
    

def format_date(val):
    if isinstance(val, datetime):
        return val.strftime('%Y-%m-%d %H:%M:%S')
    elif isinstance(val, (date)):
        return val.strftime('%Y-%m-%d')
    return val