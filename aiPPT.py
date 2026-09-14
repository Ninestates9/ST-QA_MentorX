import os
from aiPPT_api import *
from database_utils import connectSQL, closeSQL

def ai_generate_ppt(chapter_id):
    conn, cursor = connectSQL()
    cursor.execute("SELECT name, content FROM chapter WHERE id = %s;", (chapter_id,))
    result = cursor.fetchone()
    closeSQL(conn, cursor)
    if not result:
        return False, None, None, "章节不存在"
    
    chapter_name, markdown_text = result

    safe_name = f"{chapter_name}_{chapter_id}.md"
    md_path = os.path.join("./aiPPT/", safe_name)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(markdown_text)

    api_key = 'ak_sLcgq15srpsTEJUjfd'
    uid = 'mentorx'
    api_token = create_api_token(api_key, uid, None)
    data_url = parse_file_data(api_token, md_path, None, None)
    ppt_info = direct_generate_pptx(api_token, True, None, None, None, data_url)

    ppt_id = ppt_info['id']
    file_url = ppt_info['fileUrl']
    ppt_filename = f"{chapter_name}_{ppt_id}.pptx"
    ppt_path = os.path.join("./aiPPT/", ppt_filename)
    download(file_url, ppt_path)

    return True, ppt_path, ppt_filename, None