import os
import sqlite3
from shutil import copy2
from datetime import datetime

def insert_assignment(assignment_name, assignment_description, question_file, mark_scheme_file, resource_files=None):
    # Connect to the SQLite database
    conn = sqlite3.connect('my_database.db')
    cursor = conn.cursor()

    # Create the assignments and files tables if they don't exist
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS assignments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        assignment_name TEXT NOT NULL,
        assignment_description TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS files (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        assignment_id INTEGER NOT NULL,
        file_path TEXT NOT NULL,
        file_type TEXT CHECK(file_type IN ('question', 'mark_scheme', 'resource')) NOT NULL,
        FOREIGN KEY (assignment_id) REFERENCES assignments(id),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')

    # Insert the assignment (name and description)
    cursor.execute('''
    INSERT INTO assignments (assignment_name, assignment_description)
    VALUES (?, ?)''', (assignment_name, assignment_description))

    # Get the ID of the newly inserted assignment
    assignment_id = cursor.lastrowid

    # Insert the question file and mark scheme file into the files table
    cursor.execute('''
    INSERT INTO files (assignment_id, file_path, file_type)
    VALUES (?, ?, ?)''', (assignment_id, question_file, 'question'))

    cursor.execute('''
    INSERT INTO files (assignment_id, file_path, file_type)
    VALUES (?, ?, ?)''', (assignment_id, mark_scheme_file, 'mark_scheme'))

    # Insert optional resource files
    if resource_files:
        for resource in resource_files:
            cursor.execute('''
            INSERT INTO files (assignment_id, file_path, file_type)
            VALUES (?, ?, ?)''', (assignment_id, resource, 'resource'))

    # Commit the transaction and close the connection
    conn.commit()
    conn.close()


