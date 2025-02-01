from flask import Flask, render_template, request
import os
import createAssignment as ca

app = Flask(__name__)

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
    return render_template('teacher.html')

@app.route('/uploadAssignment')
def uploadAssignment():
    assignment_name = request.form['assignmentName']
    task_description = request.form['taskDescription']
    question_file = request.files['questionFile']
    markscheme_file = request.files['markschemeFile']
    resource_files = request.files.getlist('resourceFiles')
    ai_help_level = request.form['aiHelpLevel']

    assignmentId = ca.create_assignment(assignment_name, task_description, ai_help_level)
    ca.create_files
    
    UPLOAD_FOLDER = 'uploads'  # Set a folder where the uploaded files will be stored
    app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
    
    question_file_path = os.path.join(app.config['UPLOAD_FOLDER'], question_file.filename + assignmentId)
    question_file.save(question_file_path)
    
    markscheme_file_path = os.path.join(app.config['UPLOAD_FOLDER'], markscheme_file.filename + assignmentId)
    markscheme_file.save(markscheme_file_path)
    
    resource_file_paths = []
    for file in resource_files:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename + assignmentId)
        file.save(file_path)
        resource_file_paths.append(file_path)
    
    ca.create_files(assignmentId, question_file_path, markscheme_file_path, resource_file_paths)
    
if __name__ == '__main__':
    app.run(debug=True)
