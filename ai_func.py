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
    
    # Get student uploads if available
    student_uploads = get_student_uploads(assignment_id, student_name) if student_name else []
    
    # Create initial system message with clearer context and stricter help levels
    system_message = (
        "You are a teacher AI assistant. Format all responses in markdown for better readability. "
        "Use headers (##), bullet points, numbered lists, and other markdown features to structure your responses clearly. "
        "Always use line breaks between sections for clarity.\n\n"
        "Your role is to guide students towards understanding without providing direct solutions. "
        "\n\nHelp Level Guidelines (strictly follow these):"
        "\n\n10: Ask only Socratic questions to help students discover the path themselves."
        "\nExample: 'What do you think happens when...?' or 'Can you identify the key elements in...?'"
        
        "\n\n7-9: Provide general conceptual reminders and ask guiding questions."
        "\nExample: 'Remember that when dealing with X, we usually consider Y. What might that suggest here?'"
        
        "\n\n4-6: Give a structured approach without specific hints."
        "\nExample: 'Here are some key points to consider:"
        "\n- Review the relationship between X and Y"
        "\n- Consider the conditions given"
        "\n- Think about similar problems you've solved'"
        
        "\n\n1-3: Only validate student's own understanding or provide basic factual information."
        "\nExample: 'Yes, that formula is correct' or 'This type of problem typically involves [basic concept]'"
        
        "\n\nCritical Rules:"
        "\n1. Never reveal solutions or key steps"
        "\n2. Never mention the help level or mark scheme"
        "\n3. Lower help levels (1-3) should feel almost frustratingly unhelpful"
        "\n4. Higher help levels should still require significant student effort"
        "\n5. Focus on process and understanding, not answers"
        "\n6. If a student seems stuck, prioritize asking what they've tried so far"
    )
    
    # Create file content array with clear section markers
    content = [{
        "type": "text", 
        "text": (
            f"Help Level: {ai_help_level}/10 (where 10 still requires student effort)\n"
            f"Student Question: {user_question}\n\n"
            f"=== TEACHER PROVIDED MATERIALS ===\n"
            f"Below are the official assignment materials provided by your teacher:\n"
        )
    }]
    
    # Add teacher materials with labels
    content.append({"type": "text", "text": "QUESTION PAPER:"})
    content.append(get_file_content(question_file_path))
    
    content.append({"type": "text", "text": "\nMARK SCHEME:"})
    content.append(get_file_content(mark_scheme_file_path))
    
    if resources_file_paths:
        content.append({"type": "text", "text": "\nADDITIONAL RESOURCES:"})
        for file_path in resources_file_paths:
            content.append(get_file_content(file_path))
    
    # Add student materials if available
    if student_uploads:
        content.append({
            "type": "text", 
            "text": "\n=== STUDENT SUBMITTED WORK ===\nBelow are the materials you have submitted so far:"
        })
        for upload in student_uploads:
            content.append(get_file_content(upload))
    
    # Get conversation history
    messages = []
    if student_name:
        from app import get_chat_history  # Import here to avoid circular import
        chat_history = get_chat_history(student_name, assignment_id)
        if chat_history['conversation']:
            content.append({
                "type": "text",
                "text": "\n=== PREVIOUS CONVERSATION ===\nHere are your previous questions and my answers:"
            })
            messages.extend(chat_history['conversation'])
    
    # Add current question with context
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

def get_ai_summary(chat_history):
    client = anthropic.Anthropic()
    if (len(chat_history) == 0):
        return None
    chat_history_string = "\n".join([f"Student: {row[0]}, Question: {row[1]}, Answer: {row[2]}" for row in chat_history])
    system_message = "You are a teaching assistant. You need to summarise the results of the various chat histories of the students you will be given to identify which topics students in general struggled in to give to the teacher. Do not focus on one student just because they have messaged a lot. Each student's issues should be valued equally, no matter how much history they have. Give the teacher some advice about what they should focus on in their lessons. If a student seems to be particularly struggling more than the rest of the class, identify them."
    message = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=1000,
        temperature=0,
        system=system_message,
        messages=[{
        "role": "user",
        "content": chat_history_string
    }]
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

def get_student_uploads(assignment_id, student_name):
    """Get all files uploaded by a student for a specific assignment"""
    query = """
    SELECT file_path FROM student_uploads 
    WHERE assignment_id = ? AND student_name = ?
    ORDER BY timestamp ASC;
    """
    
    with sqlite3.connect('my_database.db') as conn:
        cursor = conn.cursor()
        cursor.execute(query, (assignment_id, student_name))
        file_paths = [row[0] for row in cursor.fetchall()]
    
    return file_paths