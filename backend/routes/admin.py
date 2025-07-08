from flask import Blueprint, render_template, session, redirect, request, flash
from db import get_db_connection
import bcrypt
import mysql.connector

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/admin/dashboard')
def admin_dashboard():
    if session.get('role') != 'admin':
        return redirect('/login')

    role_filter = request.args.get('role')
    org_filter = request.args.get('org')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Summary counts
    cursor.execute("SELECT COUNT(*) AS total_users FROM users WHERE role != 'admin'")
    total_users = cursor.fetchone()['total_users']
    cursor.execute("SELECT COUNT(*) AS testers FROM users WHERE role = 'tester'")
    testers = cursor.fetchone()['testers']
    cursor.execute("SELECT COUNT(*) AS developers FROM users WHERE role = 'developer'")
    developers = cursor.fetchone()['developers']
    cursor.execute("SELECT COUNT(*) AS managers FROM users WHERE role = 'manager'")
    managers = cursor.fetchone()['managers']
    cursor.execute("SELECT COUNT(*) AS projects FROM projects")
    projects = cursor.fetchone()['projects']

    # Users filtering
    query = "SELECT * FROM users WHERE role != 'admin'"
    filters = []
    params = []

    if role_filter:
        filters.append("role = %s")
        params.append(role_filter)
    if org_filter:
        filters.append("organization LIKE %s")
        params.append(f"%{org_filter}%")

    if filters:
        query += " AND " + " AND ".join(filters)

    cursor.execute(query, params)
    users = cursor.fetchall()

    # All projects
    cursor.execute("""
        SELECT p.*, u.username AS creator
        FROM projects p
        JOIN users u ON p.created_by = u.user_id
        ORDER BY p.created_at DESC
    """)
    project_list = cursor.fetchall()

    cursor.close()
    conn.close()

    summary = {
        'total_users': total_users,
        'testers': testers,
        'developers': developers,
        'managers': managers,
        'projects': projects
    }

    return render_template('admin_dashboard.html',
                           users=users,
                           projects=project_list,
                           summary=summary)


@admin_bp.route('/admin/users/create', methods=['GET', 'POST'])
def create_user():
    if session.get('role') != 'admin':
        return redirect('/login')

    if request.method == 'POST':
        username = request.form['username']
        name = request.form['name']
        password = request.form['password']
        role = request.form['role']
        organization = request.form['organization']

        # DB insert
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        existing = cursor.fetchone()
        if existing:
            flash("Username already exists.", "error")
            return redirect('/admin/users/create')

        hashed_pw = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        cursor.execute("""
            INSERT INTO users (username, name, password, role, organization)
            VALUES (%s, %s, %s, %s, %s)
        """, (username, name, hashed_pw.decode('utf-8'), role, organization))

        conn.commit()
        cursor.close()
        conn.close()

        flash("User created successfully.", "success")
        return redirect('/admin/dashboard')

    return render_template('admin_create_user.html')



@admin_bp.route('/admin/users/<int:user_id>/edit', methods=['GET', 'POST'])
def edit_user(user_id):
    if session.get('role') != 'admin':
        return redirect('/login')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    if request.method == 'POST':
        name = request.form['name']
        role = request.form['role']
        organization = request.form['organization']

        cursor.execute("""
            UPDATE users SET name = %s, role = %s, organization = %s WHERE user_id = %s
        """, (name, role, organization, user_id))
        conn.commit()
        cursor.close()
        conn.close()
        flash("User updated successfully.", "success")
        return redirect('/admin/dashboard')

    # GET request – load user
    cursor.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
    user = cursor.fetchone()
    cursor.close()
    conn.close()

    if not user or user['role'] == 'admin':
        return "User not found or cannot edit admin", 404

    return render_template('admin_edit_user.html', user=user)

@admin_bp.route('/admin/users/<int:user_id>/delete', methods=['POST'])
def delete_user(user_id):
    if session.get('role') != 'admin':
        return redirect('/login')

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # First, delete dependent feedbacks manually
        cursor.execute("DELETE FROM feedback WHERE user_id = %s", (user_id,))
    
        # Then delete the user
        cursor.execute("DELETE FROM users WHERE user_id = %s AND role != 'admin'", (user_id,))
    
        conn.commit()
        flash("User deleted successfully.", "success")
    except mysql.connector.Error as e:
        flash(f"Error deleting user: {e}", "danger")

    cursor.close()
    conn.close()
    return redirect('/admin/dashboard')
