from flask import Flask, render_template, request, redirect, url_for, jsonify, session, send_from_directory
from markupsafe import Markup
import os
import createAssignment as ca
import sqlite3
from ai_func import get_ai_response
from datetime import datetime
import markdown
from markdown.extensions.extra import ExtraExtension

app = Flask(__name__)
app.secret_key = 'your_secret_key'

# Set the upload folder globally
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def create_assignment_table() -> bool:
    # Connect to the SQLite database
    conn = sqlite3.connect('my_database.db')
    cursor = conn.cursor()

    # Create the assignments and files tables if they don't exist
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS assignments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        assignment_name TEXT NOT NULL,
        assignment_description TEXT NOT NULL,
        ai_help_level INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    conn.commit()
    conn.close()

def create_files_table() -> bool:

    conn = sqlite3.connect('my_database.db')
    cursor = conn.cursor()
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS files (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        assignment_id INTEGER NOT NULL,
        file_path TEXT NOT NULL,
        file_type TEXT CHECK(file_type IN ('question', 'mark_scheme', 'resource')) NOT NULL,
        FOREIGN KEY (assignment_id) REFERENCES assignments(id)
    )''')

    conn.commit()
    conn.close()

def create_student_uploads_table() -> bool:
    conn = sqlite3.connect('my_database.db')
    cursor = conn.cursor()
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS student_uploads (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_name TEXT NOT NULL,
        assignment_id INTEGER NOT NULL,
        question TEXT,
        file_path TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (assignment_id) REFERENCES assignments(id)
    )''')
    
    conn.commit()
    conn.close()

def create_chat_history_table() -> bool:
    conn = sqlite3.connect('my_database.db')
    cursor = conn.cursor()
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS chat_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_name TEXT NOT NULL,
        assignment_id INTEGER NOT NULL,
        question TEXT NOT NULL,
        answer TEXT NOT NULL,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (assignment_id) REFERENCES assignments(id)
    )''')
    
    conn.commit()
    conn.close()

def create_tables():
    create_assignment_table()
    create_files_table()
    create_student_uploads_table()
    create_chat_history_table()

def get_assignments():
    create_tables()
    conn = sqlite3.connect('my_database.db')
    cursor = conn.cursor()
    cursor.execute('''
    SELECT a.id, a.assignment_name, a.assignment_description, a.ai_help_level, f.file_path, f.file_type
    FROM assignments a
    LEFT JOIN files f ON a.id = f.assignment_id
    ''')
    rows = cursor.fetchall()
    conn.close()

    assignments = {}
    for row in rows:
        assignment_id, name, description, ai_help_level, file_path, file_type = row
        if assignment_id not in assignments:
            assignments[assignment_id] = {
                'id': assignment_id,  # Add this line to include the ID
                'name': name,
                'taskDescription': description,
                'aiHelpLevel': ai_help_level,
                'questionFile': '',
                'markschemeFile': '',
                'resourceFiles': []
            }
        if file_type == 'question':
            assignments[assignment_id]['questionFile'] = file_path
        elif file_type == 'mark_scheme':
            assignments[assignment_id]['markschemeFile'] = file_path
        elif file_type == 'resource':
            assignments[assignment_id]['resourceFiles'].append(file_path)

    return list(assignments.values())

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/studentLogin', methods=['GET', 'POST'])
def studentLogin():
    if request.method == 'POST':
        student_name = request.form['studentName']
        session['student_name'] = student_name
        return redirect(url_for('student'))
    return render_template('studentLogin.html')

@app.route('/student')
def student():
    student_name = session.get('student_name')
    if not student_name:
        return redirect(url_for('studentLogin'))
    assignments = get_assignments()
    return render_template('student.html', student_name=student_name, assignments=assignments)

def get_assignment_help_level(assignment_id):
    conn = sqlite3.connect('my_database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT ai_help_level FROM assignments WHERE id = ?', (assignment_id,))
    result = cursor.fetchone()
    conn.close()
    
    if result is None:
        raise ValueError(f"Assignment with ID {assignment_id} not found")
        
    return result[0]

def get_chat_history(student_name, assignment_id):
    """Returns chat history in two formats: display format and AI conversation format"""
    conn = sqlite3.connect('my_database.db')
    cursor = conn.cursor()
    cursor.execute('''
    SELECT question, answer, timestamp
    FROM chat_history
    WHERE student_name = ? AND assignment_id = ?
    ORDER BY timestamp ASC
    ''', (student_name, assignment_id))
    history = cursor.fetchall()
    conn.close()
    
    # Format history for AI context
    formatted_history = []
    for q, a, _ in history:  # Ignore timestamp for AI format
        formatted_history.extend([
            {"role": "user", "content": q},
            {"role": "assistant", "content": a}
        ])
    
    return {
        'display': history,  # For template display
        'conversation': formatted_history  # For AI context
    }

@app.route('/studentHelp', methods=['POST'])
def studentHelp():
    student_name = session.get('student_name')
    assignment_id = request.form['assignmentId']
    question = request.form['question']
    
    try:
        # Get AI help level from the assignment
        ai_help_level = get_assignment_help_level(assignment_id)
        
        # Only handle file upload if a file was actually submitted
        if 'answerFile' in request.files and request.files['answerFile'].filename != '':
            answer_file = request.files['answerFile']
            answer_folder = os.path.join(app.config['UPLOAD_FOLDER'], 'answers')
            os.makedirs(answer_folder, exist_ok=True)
            
            answer_file_path = os.path.join(answer_folder, f"{student_name}_{assignment_id}_{answer_file.filename}")
            answer_file.save(answer_file_path)
            
            # Store file upload in database
            conn = sqlite3.connect('my_database.db')
            cursor = conn.cursor()
            cursor.execute('''
            INSERT INTO student_uploads (student_name, assignment_id, question, file_path)
            VALUES (?, ?, ?, ?)''', (student_name, assignment_id, question, answer_file_path))
            conn.commit()
            conn.close()
        
        # Get AI response with conversation history
        ai_response = get_ai_response(question, ai_help_level, assignment_id, student_name)[0]
        # Use markdown with extensions for better parsing
        response_text = markdown.markdown(
            ai_response.text,
            extensions=['extra', 'nl2br', 'sane_lists']
        )
        
        # Store chat in database
        conn = sqlite3.connect('my_database.db')
        cursor = conn.cursor()
        cursor.execute('''
        INSERT INTO chat_history (student_name, assignment_id, question, answer)
        VALUES (?, ?, ?, ?)''', (student_name, assignment_id, question, response_text))
        conn.commit()
        conn.close()
        
        return redirect(url_for('chat', assignment_id=assignment_id))
    
    except ValueError as e:
        return jsonify({'error': str(e)}), 404

@app.route('/chat/<assignment_id>')
def chat(assignment_id):
    student_name = session.get('student_name')
    if not student_name:
        return redirect(url_for('studentLogin'))
    
    chat_history = get_chat_history(student_name, assignment_id)['display']  # Use display format
    ai_help_level = get_assignment_help_level(assignment_id)
    
    return render_template('chat.html', 
                         student_name=student_name,
                         assignment_id=assignment_id,
                         chat_history=chat_history,
                         ai_help_level=ai_help_level)

@app.route('/chat_message', methods=['POST'])
def chat_message():
    student_name = session.get('student_name')
    assignment_id = request.form['assignmentId']
    question = request.form['question']
    
    ai_help_level = get_assignment_help_level(assignment_id)
    ai_response = get_ai_response(question, ai_help_level, assignment_id, student_name)[0]
    response_text = markdown.markdown(
        ai_response.text,
        extensions=['extra', 'nl2br', 'sane_lists']
    )
    
    conn = sqlite3.connect('my_database.db')
    cursor = conn.cursor()
    cursor.execute('''
    INSERT INTO chat_history (student_name, assignment_id, question, answer)
    VALUES (?, ?, ?, ?)''', (student_name, assignment_id, question, response_text))
    conn.commit()
    conn.close()
    
    return jsonify({'message': response_text})

@app.route('/teacher')
def teacher():
    assignments = get_assignments()
    return render_template('teacher.html', assignments=assignments)

@app.route('/uploadAssignment', methods=['POST'])
def uploadAssignment():
    assignment_name = request.form['assignmentName']
    task_description = request.form['taskDescription']
    question_file = request.files['questionFile']
    markscheme_file = request.files['markschemeFile']
    resource_files = request.files.getlist('resourceFiles')
    ai_help_level = request.form['aiHelpLevel']

    assignmentId = str(ca.create_assignment(assignment_name, task_description, ai_help_level))
    ca.create_files
    
    UPLOAD_FOLDER = 'uploads'  # Set a folder where the uploaded files will be stored
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)  # Create uploads directory if it doesn't exist
    app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
    
    question_file_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{assignmentId}_{question_file.filename}")
    question_file.save(question_file_path)
    
    markscheme_file_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{assignmentId}_{markscheme_file.filename}")
    markscheme_file.save(markscheme_file_path)
    
    resource_file_paths = []
    for file in resource_files:
        if file.filename:  # Only process files that have a filename
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{assignmentId}_{file.filename}")
            file.save(file_path)
            resource_file_paths.append(file_path)
    
    ca.create_files(assignmentId, question_file_path, markscheme_file_path, resource_file_paths)
    
    # Redirect back to the main teacher page
    return redirect(url_for('teacher'))

@app.route('/upload', methods=['POST'])
def upload():
    assignment_id = request.form['assignmentId']
    answer_file = request.files['answerFile']
    
    answer_folder = os.path.join(app.config['UPLOAD_FOLDER'], 'answers')
    os.makedirs(answer_folder, exist_ok=True)  # Create answers directory if it doesn't exist
    
    answer_file_path = os.path.join(answer_folder, f"{assignment_id}_{answer_file.filename}")
    answer_file.save(answer_file_path)
    
    # You can add code here to save the answer file information to the database if needed
    
    return redirect(url_for('student'))

@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/assignment/<int:assignment_id>')
def assignment_details(assignment_id):
    """Shows assignment details and students who accessed it."""
    conn = sqlite3.connect('my_database.db')
    cursor = conn.cursor()

    # Get assignment details
    cursor.execute('SELECT assignment_name, assignment_description FROM assignments WHERE id = ?', (assignment_id,))
    assignment = cursor.fetchone()

    # Get students who accessed this assignment
    cursor.execute('''
    SELECT DISTINCT student_name 
    FROM chat_history 
    WHERE assignment_id = ? 
    ORDER BY student_name
    ''', (assignment_id,))
    
    students = [row[0] for row in cursor.fetchall()]
    
    conn.close()

    if not assignment:
        return "Assignment not found", 404

    return render_template('assignment_details.html', assignment_id=assignment_id, 
                           assignment_name=assignment[0], 
                           assignment_description=assignment[1], 
                           students=students)

if __name__ == '__main__':
    app.run(debug=True)
