import anthropic
import sqlite3
from pathlib import Path
import base64
import mimetypes

def get_ai_response(user_question, ai_help_level, assignment_id, student_name=None):
    client = anthropic.Anthropic()
    
    # Get files content
    file_paths = get_files(assignment_id)
    question_file_path = file_paths[0]
    mark_scheme_file_path = file_paths[1]
    resources_file_paths = file_paths[2:] if len(file_paths) > 2 else []
    
    # Create initial system message
    system_message = (
        "You are a teacher AI assistant. Your role is to answer students' questions about their homework, "
        "using the mark scheme and resources provided. You should maintain consistency with your previous "
        "answers in the conversation and build upon previous explanations when appropriate."
    )
    
    # Create file content array
    content = [{
        "type": "text", 
        "text": f"Based on a rating of {ai_help_level} out of 10 for how much you should help, "
                f"and even at 10 you should not be giving the whole answer, please answer: {user_question}\n\n"
                f"The first file is the homework questions, the second is the mark scheme, "
                f"followed by any additional resources."
    }]
    
    # Add file contents
    content.append(get_file_content(question_file_path))
    content.append(get_file_content(mark_scheme_file_path))
    for file_path in resources_file_paths:
        content.append(get_file_content(file_path))
    
    # Get conversation history if student_name is provided
    messages = []
    if student_name:
        from app import get_chat_history  # Import here to avoid circular import
        chat_history = get_chat_history(student_name, assignment_id)
        messages.extend(chat_history['conversation'])
    
    # Add current question
    messages.append({
        "role": "user",
        "content": content
    })
    
    # Get Claude's response
    message = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=1000,
        temperature=0,
        system=system_message,
        messages=messages
    )
    
    return message.content


def get_files(assignment_id):
    query = """
    SELECT file_path FROM files 
    WHERE assignment_id = ?
    ORDER BY 
        CASE file_type 
            WHEN 'question' THEN 1 
            WHEN 'mark_scheme' THEN 2 
            WHEN 'resource' THEN 3 
        END;
    """
    
    with sqlite3.connect('my_database.db') as conn:
        cursor = conn.cursor()
        cursor.execute(query, (assignment_id,))
        file_paths = [row[0] for row in cursor.fetchall()] 

    return file_paths


def get_file_content(file_path):
    file_ext = Path(file_path).suffix.lower()
    
    # Image files need specific media types
    image_types = {
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.gif': 'image/gif',
        '.webp': 'image/webp'
    }
    
    if file_ext in image_types:
        with open(file_path, "rb") as file:
            file_bytes = file.read()
        return {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": image_types[file_ext],
                "data": base64.b64encode(file_bytes).decode()
            }
        }
    
    # All other files are treated as documents
    else:
        mimetyp, encoding = mimetypes.guess_type(file_path)
        try:
            with open(file_path, "rb") as file:
                file_bytes = file.read()
            return {
            "type": "document",
            "source": {
                "type": "base64",
                "media_type": mimetyp,
                "data": base64.b64encode(file_bytes).decode()
            }
            }
        except UnicodeDecodeError:
            # If we can't read as text, return a message
            return {
                "type": "text",
                "text": f"File {Path(file_path).name} is a binary file and cannot be processed directly."
            }