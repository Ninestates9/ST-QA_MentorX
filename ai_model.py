from X1_http import get_answer
from database_utils import connectSQL, closeSQL, commit_exercise_db, search_worst_chapter, get_chapter_practice_history_db
from ocr import ocr
from langchain.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings


embedding_model = HuggingFaceEmbeddings(model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
db = FAISS.load_local("./multi_doc_vector_db", embedding_model, allow_dangerous_deserialization=True)

def ai_generate_teachcontent(Cno, chapter):
    conn, cursor = connectSQL()
    try:        
        cursor.execute("SELECT name FROM course WHERE id = %s;", (Cno,))
        result = cursor.fetchone()
        Cname = result[0] if result else "暂无课程名"
    except:
        return False, None
    
    query = f"{Cname} {chapter}"
    context = db.similarity_search(query, k=3)

    full_prompt = f"""
    你是一位教学设计专家，请根据以下资料生成一份教学内容，要求包括：

    1. 知识讲解内容(必须详细具体，可以根据资料进行拓展，每个具体知识点不少于300字)
    2. 实训练习安排（不少于2个）
    3. 指导建议（学生应掌握哪些技能/难点）
    4. 时间分布（理论与实践分配）

    【课程资料】{context}
    【课程名】{Cname}
    【章节名】{chapter}
    """
    try:
        content = get_answer(full_prompt)
        sql = "INSERT INTO chapter(name, content, course_id) values(%s, %s, %s);"
        cursor.execute(sql, (chapter, content, Cno))
        return True, None
    except Exception as e:
        print(f"ERROR: {e}")
        return False, e
    finally:
        closeSQL(conn, cursor)

def ai_generate_tasks(ChapterNo, difficulty, type, student_id = None):
    conn, cursor = connectSQL()
    try:
        cursor.execute("SELECT content FROM chapter WHERE id = %s;", (ChapterNo,))
        result = cursor.fetchone()
        content = result[0] if result else "无内容"
    except:
        return False
    
    difficulty_map = {
        4 : "极难",
        3 : "困难",
        2 : "中等",
        1 : "简单"
    }

    type_map = {
        'choices': '选择题',
        'blanks': '填空题',
        'answers': '简答题',
        'code': '编程题'
    }
    TYPE = type_map.get(type, '简答题')  
    DIFFI = difficulty_map.get(difficulty, "中等")

    full_prompt = f"""请根据以下课件内容和要求设计一道练习题目，只用生成一道， 仅生成题目，不需要答案；
    课件内容：
    {content}
    难度等级：
    {DIFFI}
    题目类型：
    {TYPE}
    """
    try:
        exercise = get_answer(full_prompt)
        new_prompt = f"""请根据以下课件内容和题目类型，给出练习题目的答案，要求去掉分析；
        课件内容：
        {content}
        题目类型：
        {TYPE}
        题目：
        {exercise}
        """

        answer = get_answer(new_prompt)
        if student_id:
            sql = '''INSERT INTO exercise(exercise_content, answer, difficulty, type, chapter_id, is_official, student_id, is_daily)
            VALUES(%s, %s, %s, %s, %s, 0, %s, 0);
            '''
            cursor.execute(sql, (exercise, answer, difficulty, type, ChapterNo, student_id))
        else:
            sql = '''INSERT INTO exercise(exercise_content, answer, difficulty, type, chapter_id, is_official, is_daily)
            VALUES(%s, %s, %s, %s, %s, 1, 0);
            '''
            cursor.execute(sql, (exercise, answer, difficulty, type, ChapterNo))
        return True
    except:
        return False
    finally:
        closeSQL(conn, cursor)

def ai_generate_daily_tasks(student_id):
    conn, cursor = connectSQL()
    chapter_id = search_worst_chapter(student_id)

    cursor.execute("SELECT content FROM chapter WHERE id = %s;", (chapter_id,))
    result = cursor.fetchone()
    content = result[0] if result else "无内容"

    practice_history_rows = get_chapter_practice_history_db(student_id, chapter_id)
    keys = ["exercise_content", "student_answer", "analyse", "check"]
    practice_history_dicts = [dict(zip(keys, row)) for row in practice_history_rows]
    full_prompt = f"""请根据以下课件内容和学生做题历史记录设计一道针对性的练习题目，只用生成一道， 仅生成题目，不需要答案，涉及知识覆盖学生的错误点，题目类型不限，选择题、简答题、填空题、编程题均可；
    课件内容：
    {content}
    学生历史做题记录，其中“check”字段，0代表正确，1代表错误，2代表部分正确：
    {practice_history_dicts}
    """
    try:
        exercise = get_answer(full_prompt)
        new_prompt = f"""请根据以下课件内容，给出练习题目的答案，要求去掉分析；
        课件内容：
        {content}
        题目：
        {exercise}
        """
        answer = get_answer(new_prompt)     
        sql = '''INSERT INTO exercise(exercise_content, answer, chapter_id, student_id, is_daily, exercise_date)
        VALUES(%s, %s, %s, %s, 1, CURRENT_DATE);
        '''
        cursor.execute(sql, (exercise, answer, chapter_id, student_id))
        return True
    except:
        return False
    finally:
        closeSQL(conn, cursor)

def ai_check_answer(Eno, student_id):
    conn, cursor = connectSQL()
    cursor.execute("SELECT exercise_content, answer FROM exercise WHERE id = %s;", (Eno,))
    result = cursor.fetchone()
    if result:
        content = result[0]
        answer = result[1]
    else:
        return False, "该习题不存在！"
    
    cursor.execute("SELECT student_answer FROM practice_history WHERE student_id = %s AND exercise_id = %s;", (student_id, Eno))
    result = cursor.fetchone()
    if result:
        student_answer = result[0]
    else:
        return False, "该习题未作答！"
    
    full_prompt = f"""请批改练习题，要求仅给出一个数字，0代表正确，1代表错误，2代表部分正确
    题目：
    {content}
    参考答案：
    {answer}
    学生答案：
    {student_answer}
    """
    try:
        check = get_answer(full_prompt)     
        new_prompt = f"""请根据参考答案与学生答案，给出该学生作答的分析，指出关键点、错误点和可以改进的地方；
        题目：
        {content}
        参考答案：
        {answer}
        学生答案：
        {student_answer}
        """
        analyse = get_answer(new_prompt)

        try:
            sql = "UPDATE practice_history SET analyse = %s, `check` = %s WHERE student_id = %s AND exercise_id = %s;"
            cursor.execute(sql, (analyse, check, student_id, Eno))
            return True, None
        except:
            return False, "数据库操作异常！"
    except:
        return False, "模型调用异常！"
    finally:
        closeSQL(conn, cursor)

def ai_aichat(student_id, chapter_id, content, session_id):
    conn, cursor = connectSQL()      
    cursor.execute("SELECT content FROM chapter WHERE id = %s", (chapter_id,))
    result = cursor.fetchone()
    if result:
        teachcontent = result[0]
    else:
        return False, "该章节无内容！"

    full_prompt = f"""请根据以下课件内容回答问题。
    课件内容：{teachcontent}   
    问题：{content}
    """
    try:
        answer = get_answer(full_prompt)
        try:
            if session_id == -1:
                cursor.execute("SELECT MAX(session_id) FROM communicate_history;") 
                res = cursor.fetchone()[0]
                session_id = res + 1 if res else 1
            sql = "INSERT INTO communicate_history values(%s, %s, 'Q', %s, CURRENT_TIMESTAMP, %s, '默认名称');"
            cursor.execute(sql, (student_id, chapter_id, content, session_id))
            sql = "INSERT INTO communicate_history values(%s, %s, 'A', %s, CURRENT_TIMESTAMP + INTERVAL 3 SECOND, %s, '默认名称');"
            cursor.execute(sql, (student_id, chapter_id, answer, session_id))
            return True, answer
        except:
            return False, "数据库操作异常！"
    except:
        return False, "模型输出结果异常！"
    finally:
        closeSQL(conn, cursor)

def ai_generate_suggestion(chapter_id):
    conn, cursor = connectSQL()
    cursor.execute("SELECT content FROM chapter WHERE id = %s;", (chapter_id,))
    result = cursor.fetchone()
    if result:
        content = result[0]
    else:
        return False, "该章节无内容！"
    sql = '''
    SELECT exercise_content, answer, student_answer, analyse, `check`
    FROM exercise, practice_history
    WHERE exercise.chapter_id = %s
    AND exercise.id = practice_history.exercise_id
    AND student_answer IS NOT NULL
    AND analyse IS NOT NULL;
    '''
    cursor.execute(sql, (chapter_id,))
    practice_history_rows = cursor.fetchall()
    keys = ["exercise_content", "right_answer", "student_answer", "analyse", "check"]
    practice_history_dicts = [dict(zip(keys, row)) for row in practice_history_rows]
    full_prompt = f"""请根据以下课件内容和学生做题历史记录，总结学生知识掌握情况，给出教学建议，要求包括：
    1. 详细具体的知识点掌握情况
    2. 学习难点和易错点
    3. 针对性的练习建议
    4. 下一阶段的教学重点 
    课件内容：
    {content}
    学生历史做题记录，其中“analyse”字段表示对学生该题作答的分析，“check”字段，0代表正确，1代表错误，2代表部分正确：
    {practice_history_dicts}
    """
    try:
        suggestion = get_answer(full_prompt)
        sql = "UPDATE chapter SET suggestion = %s, suggestion_time = CURRENT_TIMESTAMP WHERE id = %s;"
        cursor.execute(sql, (suggestion, chapter_id))
        return True, None
    except Exception as e:
        print(f"ERROR: {e}")
        return False, e
    finally:
        closeSQL(conn, cursor)

def ai_img2word(student_id, exercise_id, img_path):
    student_answer = ocr(picFilePath = img_path)
    success = commit_exercise_db(student_id, exercise_id, student_answer)
    return success, None