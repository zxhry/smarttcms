from flask import Blueprint, render_template, request, session, redirect
from db import get_db_connection

manager_bp = Blueprint('manager', __name__)

@manager_bp.route('/manager/dashboard')
def manager_dashboard():
    if session.get('role') != 'manager':
        return redirect('/login')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Get test case status summary
    cursor.execute("""
     SELECT status, COUNT(*) as count 
     FROM test_cases 
     WHERE project_id IN (
         SELECT project_id FROM projects WHERE organization = %s
     )
     GROUP BY status
    """, (session['organization'],))

    status_counts = {'pass': 0, 'fail': 0, 'in review': 0}
    for row in cursor.fetchall():
        status = row['status'].lower()
        if status in status_counts:
            status_counts[status] = row['count']

    # Get projects list for this manager's org
    cursor.execute("""
        SELECT p.*, u.username as creator
        FROM projects p
        JOIN users u ON p.created_by = u.user_id
        WHERE p.organization = %s
        ORDER BY p.created_at DESC
    """, (session['organization'],))
    projects = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('manager_dashboard.html', projects=projects, status_counts=status_counts)



@manager_bp.route('/manager/projects/<int:project_id>')
def view_project(project_id):
    if 'user_id' not in session:
        return redirect('/login')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Confirm project exists in same org
    cursor.execute("SELECT * FROM projects WHERE project_id = %s AND organization = %s",
                   (project_id, session['organization']))
    project = cursor.fetchone()
    if not project:
        return "Unauthorized or not found", 403

    # Fetch test cases in this project
    cursor.execute("""
        SELECT t.*, u.username
        FROM test_cases t
        JOIN users u ON t.created_by = u.user_id
        WHERE t.project_id = %s
        ORDER BY t.created_date DESC
    """, (project_id,))
    testcases = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template("manager_project_detail.html", project=project, testcases=testcases)
