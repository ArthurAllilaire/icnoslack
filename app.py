from flask import Flask, render_template, request, redirect, url_for, jsonify, session, send_from_directory
from markupsafe import Markup
import os
import createAssignment as ca
import sqlite3
from ai_func import get_ai_response, get_ai_summary
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
    if assignments:
        # Get first assignment as default
        default_assignment = assignments[0]
        chat_history = get_chat_history(student_name, str(default_assignment['id']))['display']
        ai_help_level = get_assignment_help_level(str(default_assignment['id']))
        
        return render_template('chat.html',
                             student_name=student_name,
                             assignment_id=str(default_assignment['id']),
                             assignments=assignments,
                             current_assignment=default_assignment,
                             chat_history=chat_history,
                             ai_help_level=ai_help_level,
                             show_welcome=True)  # New flag for welcome message
    else:
        return render_template('chat.html',
                             student_name=student_name,
                             assignments=[],
                             show_welcome=True)  # Show welcome even with no assignments

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
    
    # Get chat messages with associated file uploads
    cursor.execute('''
    SELECT ch.question, ch.answer, ch.timestamp, su.file_path
    FROM chat_history ch
    LEFT JOIN student_uploads su 
    ON ch.student_name = su.student_name 
    AND ch.assignment_id = su.assignment_id 
    AND ch.question = su.question
    WHERE ch.student_name = ? AND ch.assignment_id = ?
    ORDER BY ch.timestamp ASC
    ''', (student_name, assignment_id))
    
    history = cursor.fetchall()
    
    # Process file paths to get just the filename
    processed_history = []
    for q, a, t, file_path in history:
        if file_path:
            # Get just the filename from the full path
            filename = os.path.basename(file_path)
            processed_history.append((q, a, t, filename))
        else:
            processed_history.append((q, a, t, None))
    
    conn.close()
    
    # Format history for AI context
    formatted_history = []
    for q, a, _, _ in processed_history:  # Ignore timestamp and file_path for AI format
        formatted_history.extend([
            {"role": "user", "content": q},
            {"role": "assistant", "content": a}
        ])
    
    return {
        'display': processed_history,  # Now contains just filenames
        'conversation': formatted_history
    }

def process_response(text):
    """Process AI response text to handle both markdown and LaTeX"""
    # Temporarily replace LaTeX delimiters with placeholders
    text = text.replace('$', '§MATH§')
    
    # Convert markdown to HTML
    html = markdown.markdown(
        text,
        extensions=['extra', 'nl2br', 'sane_lists']
    )
    
    # Restore LaTeX delimiters
    html = html.replace('§MATH§', '$')
    
    return html

@app.route('/studentHelp', methods=['POST'])
def studentHelp():
    print("Headers:", request.headers)  # Debug: Print request headers
    print("Form data:", request.form)
    print("Files:", request.files)
    
    student_name = session.get('student_name')
    if not student_name:
        return jsonify({'error': 'Not logged in'}), 401
        
    assignment_id = request.form['assignmentId']
    question = request.form['question']
    
    # Get AI help level from the assignment
    ai_help_level = get_assignment_help_level(assignment_id)
    
    # Handle file upload first
    answer_file = request.files.get('answerFile')
    if answer_file and answer_file.filename:
        allowed_extensions = {'.pdf', '.txt', '.doc', '.docx', '.jpg', '.jpeg', '.png'}
        file_ext = os.path.splitext(answer_file.filename)[1].lower()
        
        if file_ext not in allowed_extensions:
            return jsonify({'error': 'Invalid file type'}), 400
        
        # Create upload directory if it doesn't exist
        answer_folder = os.path.join(app.config['UPLOAD_FOLDER'], 'answers')
        os.makedirs(answer_folder, exist_ok=True)
        
        # Generate safe filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_filename = f"{student_name}_{assignment_id}_{timestamp}{file_ext}"
        answer_file_path = os.path.join(answer_folder, safe_filename)
        
        # Save file and record in database
        answer_file.save(answer_file_path)
        
        conn = sqlite3.connect('my_database.db')
        cursor = conn.cursor()
        cursor.execute('''
        INSERT INTO student_uploads (student_name, assignment_id, question, file_path)
        VALUES (?, ?, ?, ?)''', (student_name, assignment_id, question, answer_file_path))
        conn.commit()
        conn.close()
    
    # Get new AI response
    ai_response = get_ai_response(question, ai_help_level, assignment_id, student_name)[0]
    response_text = process_response(ai_response.text)
    
    # Store chat in database
    conn = sqlite3.connect('my_database.db')
    cursor = conn.cursor()
    cursor.execute('''
    INSERT INTO chat_history (student_name, assignment_id, question, answer)
    VALUES (?, ?, ?, ?)''', (student_name, assignment_id, question, response_text))
    conn.commit()
    conn.close()
    
    # Check if this is an AJAX request
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'message': response_text})
    
    # For regular form submit, redirect to chat page
    return redirect(url_for('chat', assignment_id=assignment_id))

@app.route('/chat/<assignment_id>')
def chat(assignment_id):
    student_name = session.get('student_name')
    if not student_name:
        return redirect(url_for('studentLogin'))
    
    # Get all assignments for the sidebar
    assignments = get_assignments()
    
    # Get current assignment details
    current_assignment = next((a for a in assignments if str(a['id']) == str(assignment_id)), None)
    if not current_assignment:
        return "Assignment not found", 404
    
    chat_history = get_chat_history(student_name, assignment_id)['display']
    ai_help_level = get_assignment_help_level(assignment_id)
    
    return render_template('chat.html', 
                         student_name=student_name,
                         assignment_id=assignment_id,
                         assignments=assignments,
                         current_assignment=current_assignment,
                         chat_history=chat_history,
                         ai_help_level=ai_help_level,
                         show_welcome=False)  # Don't show welcome message in chat view

@app.route('/teacher')
def teacher():
    assignments = get_assignments()
    return render_template('teacher.html', assignments=assignments)


def summary(assignment_id):
    conn = sqlite3.connect('my_database.db')
    cursor = conn.cursor()
    cursor.execute("""
    SELECT student_name, question, answer
    FROM chat_history
    WHERE assignment_id = ?
    ORDER BY student_name, timestamp;
    """, assignment_id)
    history = cursor.fetchall()
    conn.close()
    
    ai_response = get_ai_summary(history)
    if (ai_response == None):
        return None
    else:
        # Use the same process_response function we use for chat messages
        summary_text = process_response(ai_response[0].text)
        return summary_text

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
    
    return redirect(url_for('teacher'))

@app.route('/upload', methods=['POST'])
def upload():
    assignment_id = request.form['assignmentId']
    answer_file = request.files['answerFile']
    
    answer_folder = os.path.join(app.config['UPLOAD_FOLDER'], 'answers')
    os.makedirs(answer_folder, exist_ok=True)  # Create answers directory if it doesn't exist
    
    answer_file_path = os.path.join(answer_folder, f"{assignment_id}_{answer_file.filename}")
    answer_file.save(answer_file_path)
    
    return redirect(url_for('student'))

@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    # First try in the main uploads directory
    if os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], filename)):
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)
    
    # Then try in the answers subdirectory
    answers_folder = os.path.join(app.config['UPLOAD_FOLDER'], 'answers')
    if os.path.exists(os.path.join(answers_folder, filename)):
        return send_from_directory(answers_folder, filename)
    
    return "File not found", 404

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
    
    students = [row[0] for row in cursor.fetchall()]  # List of student names
    
    conn.close()

    if not assignment:
        return "Assignment not found", 404

    # Debugging
    print("Students list:", students)  # Check if students are retrieved correctly

    return render_template('assignment_details.html', 
                           assignment_id=assignment_id, 
                           assignment_name=assignment[0], 
                           assignment_description=assignment[1], 
                           students=students, 
                           summary=summary(str(assignment_id)))

@app.route('/student_chat_history/<student_name>/<int:assignment_id>')
def student_chat_history(student_name, assignment_id):
    conn = sqlite3.connect('my_database.db')
    cursor = conn.cursor()
    
    # Fetch assignment details
    cursor.execute("SELECT id, assignment_name FROM assignments WHERE id = ?", (assignment_id,))
    assignment = cursor.fetchone()
    
    if not assignment:
        return "Assignment not found", 404
    
    # Convert to a dictionary
    assignment = {'id': assignment[0], 'name': assignment[1]}

    # Fetch chat history with the correct timestamp (ensuring it represents the AI response time)
    cursor.execute("""
    SELECT question, answer, timestamp 
    FROM chat_history 
    WHERE student_name = ? AND assignment_id = ?
    ORDER BY timestamp ASC
    """, (student_name, assignment_id))
    
    chat_history = [{'question': row[0], 'answer': row[1], 'timestamp': row[2]} for row in cursor.fetchall()]

    conn.close()

    return render_template('chat_history.html', student=student_name, assignment=assignment, chat_history=chat_history)

if __name__ == '__main__':
    app.run(debug=True)
