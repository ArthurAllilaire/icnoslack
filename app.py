from flask import Flask, render_template, request, redirect, url_for, jsonify
import os
import createAssignment as ca
import sqlite3

app = Flask(__name__)

def get_assignments():
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

@app.route('/studentLogin')
def studentLogin():
    return render_template('studentLogin.html')

@app.route('/student')
def student():
    return render_template('student.html')

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
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{assignmentId}_{file.filename}")
        file.save(file_path)
        resource_file_paths.append(file_path)
    
    ca.create_files(assignmentId, question_file_path, markscheme_file_path, resource_file_paths)
    
    # Redirect back to the main teacher page
    return redirect(url_for('teacher'))

if __name__ == '__main__':
    app.run(debug=True)
