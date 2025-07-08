from flask import Blueprint, render_template, request, redirect, session, flash
from db import get_db_connection

project_bp = Blueprint('projects', __name__)

@project_bp.route('/projects')
def list_projects():
    if 'user_id' not in session:
        return redirect('/login')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT p.project_id, p.title, p.created_at, u.name AS creator
        FROM projects p
        JOIN users u ON p.created_by = u.user_id
        WHERE p.organization = %s
        ORDER BY p.created_at DESC
    """, (session['organization'],))

    projects = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template('projects.html', projects=projects)



@project_bp.route('/projects/create', methods=['GET', 'POST'])
def create_project():
    if 'user_id' not in session:
        return redirect('/login')

    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        created_by = session['user_id']
        organization = session['organization']  # ✅ correct

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO projects (title, description, created_by, organization)
            VALUES (%s, %s, %s, %s)
        """, (title, description, created_by, organization))
        conn.commit()
        cursor.close()
        conn.close()
        flash("Project created.", "success")
        return redirect('/projects')

    return render_template('create_project.html')


@project_bp.route('/projects/<int:project_id>')
def view_project(project_id):
    if 'user_id' not in session:
        return redirect('/login')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM projects WHERE project_id = %s AND organization = %s",
                   (project_id, session['organization']))
    project = cursor.fetchone()

    if not project:
        return "Project not found or unauthorized", 404

    # ✅ Updated query to include executor name
    cursor.execute("""
        SELECT t.*, u.username AS creator, u.username AS executor
        FROM test_cases t
        JOIN users u ON t.created_by = u.user_id
        LEFT JOIN users e ON t.executed_by = e.user_id
        WHERE t.project_id = %s
    """, (project_id,))

    testcases = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('project_detail.html', project=project, testcases=testcases)
