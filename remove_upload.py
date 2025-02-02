import sqlite3
import os

def remove_invalid_uploads():
    """Remove database entries where the file path doesn't exist"""
    
    conn = sqlite3.connect('my_database.db')
    cursor = conn.cursor()
    
    # Get all file paths from student_uploads
    cursor.execute('SELECT id, file_path FROM student_uploads')
    uploads = cursor.fetchall()
    
    # Track invalid entries
    invalid_entries = []
    
    # Check each file path
    for upload_id, file_path in uploads:
        if file_path and not os.path.exists(file_path):
            invalid_entries.append(upload_id)
            print(f"Invalid path found: {file_path}")
    
    # Remove invalid entries
    if invalid_entries:
        placeholders = ','.join('?' * len(invalid_entries))
        cursor.execute(f'DELETE FROM student_uploads WHERE id IN ({placeholders})', invalid_entries)
        print(f"Removed {cursor.rowcount} invalid entries from database")
        conn.commit()
    else:
        print("No invalid entries found")
    
    conn.close()

if __name__ == "__main__":
    remove_invalid_uploads()
