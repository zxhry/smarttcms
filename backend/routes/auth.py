from flask import Blueprint, render_template, request, redirect, session, flash
from db import get_db_connection
import bcrypt

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/')
def root():
    return redirect('/login')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if user and bcrypt.checkpw(password.encode('utf-8'), user['password'].encode('utf-8')):
            session['name'] = user['name']
            session['user_id'] = user['user_id']
            session['username'] = user['username']
            session['role'] = user['role']
            session['organization'] = user['organization']

            # ✅ Redirect based on role
            if user['role'] == 'admin':
                return redirect('/admin/dashboard')
            elif user['role'] == 'manager':
                return redirect('/manager/dashboard')
            else:
                return redirect('/projects')  # Tester / Developer

        # Login failed
        flash('Invalid credentials.', 'error')

    return render_template('login.html')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        username = request.form['username'].strip().lower()  # normalize to lowercase
        password = request.form['password']
        role = request.form['role']
        organization = request.form['organization']

        # ✅ Optional: Validate allowed roles
        if role not in ['tester', 'developer', 'manager']:
            flash("Invalid role selected.", "error")
            return render_template("register.html")

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # ✅ Check for existing username (case-insensitive)
        cursor.execute("SELECT * FROM users WHERE LOWER(username) = %s", (username,))
        if cursor.fetchone():
            flash("Username already exists. Please choose another.", "error")
            return render_template("register.html")

        # ✅ Hash the password
        hashed_pw = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

        # ✅ Insert new user
        cursor.execute("""
            INSERT INTO users (name, username, password, role, organization)
            VALUES (%s, %s, %s, %s, %s)
        """, (name, username, hashed_pw.decode('utf-8'), role, organization))

        conn.commit()
        cursor.close()
        conn.close()

        flash("Registration successful. Please login.", "success")
        return redirect('/login')

    return render_template("register.html")



@auth_bp.route('/profile/edit', methods=['GET', 'POST'])
def edit_profile():
    if 'user_id' not in session:
        return redirect('/login')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Get user info including role
    cursor.execute("SELECT name, role FROM users WHERE user_id = %s", (session['user_id'],))
    user = cursor.fetchone()

    if request.method == 'POST':
        name = request.form['name']
        password = request.form['password']

        if password:
            hashed = bcrypt.generate_password_hash(password).decode('utf-8')
            cursor.execute("UPDATE users SET name = %s, password = %s WHERE user_id = %s",
                           (name, hashed, session['user_id']))
        else:
            cursor.execute("UPDATE users SET name = %s WHERE user_id = %s",
                           (name, session['user_id']))

        conn.commit()
        flash('Profile updated successfully.', 'success')
        session['name'] = name

        # Redirect based on role
        if user['role'] == 'admin':
            return redirect('/admin/dashboard')
        else:
            return redirect('/projects')

    # Pass cancel_url to the template
    cancel_url = '/admin/dashboard' if user['role'] == 'admin' else '/projects'

    return render_template('edit_profile.html', user=user, cancel_url=cancel_url)


@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect('/login')
