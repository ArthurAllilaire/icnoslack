from flask import Flask, render_template, request, redirect, url_for, jsonify, session, send_from_directory
import os
import createAssignment as ca
import sqlite3
from ai_func import get_ai_response

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

def create_tables():
    create_assignment_table()
    create_files_table()

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

@app.route('/studentHelp', methods=['POST'])
def studentHelp():
    question = request.form['question']
    ai_help_level = request.form['aiHelpLevel']
    message = get_ai_response(question, ai_help_level)
    return jsonify({'message': message})

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
    
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)  # Create uploads directory if it doesn't exist
    
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

if __name__ == '__main__':
    app.run(debug=True)
