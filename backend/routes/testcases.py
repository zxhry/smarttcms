from flask import Blueprint, render_template, request, redirect, session, flash
from db import get_db_connection
import pdfkit
from flask import make_response
from datetime import datetime

testcase_bp = Blueprint('testcases', __name__)

@testcase_bp.route('/projects/<int:project_id>/testcases/create', methods=['GET', 'POST'])
def create_testcase(project_id):
    if 'user_id' not in session:
        return redirect('/login')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM projects WHERE project_id = %s AND organization = %s",
                   (project_id, session['organization']))
    project = cursor.fetchone()

    if not project:
        return "Unauthorized or project not found", 404

    if request.method == 'POST':
        title = request.form['title']
        priority = request.form['priority']
        module_name = request.form['module_name']
        description = request.form['description']
        preconditions = request.form['preconditions']
        created_by = session['user_id']
        execution_date = request.form.get('execution_date') or None
        executed_by = created_by if execution_date else None

        cursor.execute("""
            INSERT INTO test_cases (
                project_id, title, priority, module_name, description, preconditions,
                created_by, execution_date, executed_by
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            project_id, title, priority, module_name, description, preconditions,
            created_by, execution_date, executed_by
        ))


        test_case_id = cursor.lastrowid

        # Insert each test step
        step_descriptions = request.form.getlist('step_description[]')
        step_data = request.form.getlist('step_data[]')
        step_expected = request.form.getlist('step_expected[]')

        for i in range(len(step_descriptions)):
            cursor.execute("""
                INSERT INTO test_steps (test_case_id, step_number, description, test_data, expected_result)
                VALUES (%s, %s, %s, %s, %s)
            """, (
                test_case_id,
                i + 1,
                step_descriptions[i],
                step_data[i],
                step_expected[i]
            ))


        conn.commit()
        cursor.close()
        conn.close()

        flash('Test case created.', 'success')
        return redirect(f'/projects/{project_id}')

    cursor.close()
    conn.close()
    return render_template('create_testcase.html', project=project)


@testcase_bp.route('/testcases/<int:test_case_id>', methods=['GET', 'POST'])
def view_testcase(test_case_id):
    if 'user_id' not in session:
        return redirect('/login')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Get test case
    cursor.execute("""
        SELECT t.*, p.title AS project_title, u.username AS tester
        FROM test_cases t
        JOIN projects p ON t.project_id = p.project_id
        JOIN users u ON t.created_by = u.user_id
        WHERE test_case_id = %s
    """, (test_case_id,))
    testcase = cursor.fetchone()

    # Get test steps
    cursor.execute("SELECT * FROM test_steps WHERE test_case_id = %s ORDER BY step_number", (test_case_id,))
    steps = cursor.fetchall()

    # Get feedback
    cursor.execute("""
        SELECT f.comment, f.created_at, u.username
        FROM feedback f
        JOIN users u ON f.user_id = u.user_id
        WHERE f.test_case_id = %s
        ORDER BY f.created_at DESC
    """, (test_case_id,))
    feedbacks = cursor.fetchall()

    # Submit new feedback
    if request.method == 'POST' and session['role'] == 'developer':
        comment = request.form.get('comment')
        if comment:
            cursor.execute("""
                INSERT INTO feedback (test_case_id, user_id, comment)
                VALUES (%s, %s, %s)
            """, (test_case_id, session['user_id'], comment))
            conn.commit()
            flash('Comment added.', 'success')
            return redirect(f'/testcases/{test_case_id}')

    cursor.close()
    conn.close()

    return render_template('testcase_detail.html', testcase=testcase, steps=steps, feedbacks=feedbacks)


@testcase_bp.route('/testcases/<int:test_case_id>/edit', methods=['GET', 'POST'])
def edit_testcase(test_case_id):
    if 'user_id' not in session:
        return redirect('/login')

    role = session.get('role')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT * FROM test_cases WHERE test_case_id = %s", (test_case_id,))
    testcase = cursor.fetchone()

    if not testcase or (role != 'tester' and session['user_id'] != testcase['created_by']):
        cursor.close()
        conn.close()
        return "Unauthorized or test case not found", 403

    if request.method == 'POST':
        title = request.form['title']
        priority = request.form['priority']
        module_name = request.form['module_name']
        description = request.form['description']
        preconditions = request.form['preconditions']
        status = request.form['status']
        execution_date = request.form['execution_date'] or None
        
        cursor.execute("""
            UPDATE test_cases
            SET title=%s, description=%s, preconditions=%s,
                module_name=%s, priority=%s, status=%s,
                execution_date=%s, modified_date=%s
            WHERE test_case_id = %s
        """, (title, description, preconditions,
              module_name, priority, status,
              execution_date, datetime.now(), test_case_id
            ))

        conn.commit()

        flash('Test case updated successfully.', 'success')
        return redirect(f'/testcases/{test_case_id}')

    cursor.close()
    conn.close()
    return render_template('edit_testcase.html', testcase=testcase)

@testcase_bp.route('/testcases/<int:test_case_id>/steps', methods=['GET', 'POST'])
def execute_steps(test_case_id):
    if 'user_id' not in session:
        return redirect('/login')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Get test case and steps
    cursor.execute("""
        SELECT t.*, p.title AS project_title
        FROM test_cases t
        JOIN projects p ON t.project_id = p.project_id
        WHERE t.test_case_id = %s
    """, (test_case_id,))
    testcase = cursor.fetchone()

    cursor.execute("SELECT * FROM test_steps WHERE test_case_id = %s ORDER BY step_number", (test_case_id,))
    steps = cursor.fetchall()

    if request.method == 'POST':
        # Existing steps
        step_ids = request.form.getlist('step_id[]')
        descriptions = request.form.getlist('description[]')
        test_data_list = request.form.getlist('test_data[]')
        expected_results = request.form.getlist('expected_result[]')
        actual_results = request.form.getlist('actual_result[]')
        statuses = request.form.getlist('status[]')
        notes = request.form.getlist('notes[]')
        delete_step_ids = request.form.getlist('delete_step_ids[]')  # step_id values marked for deletion

        for i in range(len(step_ids)):
            if step_ids[i] in delete_step_ids:
                cursor.execute("DELETE FROM test_steps WHERE step_id = %s", (step_ids[i],))
            else:
                cursor.execute("""
                    UPDATE test_steps 
                    SET description = %s, test_data = %s, expected_result = %s,
                        actual_result = %s, status = %s, notes = %s
                    WHERE step_id = %s AND test_case_id = %s
                """, (
                    descriptions[i], test_data_list[i], expected_results[i],
                    actual_results[i], statuses[i], notes[i], step_ids[i], test_case_id
                ))

        # New steps
        new_descriptions = request.form.getlist('new_step_description[]')
        new_test_data = request.form.getlist('new_step_data[]')
        new_expected = request.form.getlist('new_expected_result[]')

        # Determine next step number
        cursor.execute("SELECT MAX(step_number) FROM test_steps WHERE test_case_id = %s", (test_case_id,))
        result = cursor.fetchone()
        next_step_number = (result['MAX(step_number)'] or 0) + 1

        for i in range(len(new_descriptions)):
            if new_descriptions[i].strip():
                cursor.execute("""
                    INSERT INTO test_steps (test_case_id, step_number, description, test_data, expected_result)
                    VALUES (%s, %s, %s, %s, %s)
                """, (test_case_id, next_step_number, new_descriptions[i], new_test_data[i], new_expected[i]))
                next_step_number += 1

        conn.commit()
        flash("Steps updated.", "success")
        return redirect(f'/testcases/{test_case_id}/steps')

    cursor.close()
    conn.close()
    return render_template('execute_steps.html', testcase=testcase, steps=steps)


@testcase_bp.route('/testcases/<int:test_case_id>/delete', methods=['POST'])
def delete_testcase(test_case_id):
    if 'user_id' not in session:
        return redirect('/login')

    conn = get_db_connection()
    cursor = conn.cursor()

    # Optional: Confirm test case belongs to user's organization
    cursor.execute("""
        SELECT t.project_id, p.organization
        FROM test_cases t
        JOIN projects p ON t.project_id = p.project_id
        WHERE t.test_case_id = %s
    """, (test_case_id,))
    result = cursor.fetchone()

    if not result or result[1] != session['organization']:
        cursor.close()
        conn.close()
        return "Unauthorized or test case not found", 403

    # Delete related test steps and feedback
    cursor.execute("DELETE FROM feedback WHERE test_case_id = %s", (test_case_id,))
    cursor.execute("DELETE FROM test_steps WHERE test_case_id = %s", (test_case_id,))

    # Delete the test case
    cursor.execute("DELETE FROM test_cases WHERE test_case_id = %s", (test_case_id,))
    conn.commit()
    cursor.close()
    conn.close()

    flash('Test case deleted successfully.', 'success')
    return redirect(f"/projects/{result[0]}")

@testcase_bp.route('/testcases/<int:test_case_id>/download')
def download_testcase(test_case_id):
    if 'user_id' not in session:
        return redirect('/login')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Get test case
    cursor.execute("""
        SELECT t.*, p.title AS project_title, u.username AS tester
        FROM test_cases t
        JOIN projects p ON t.project_id = p.project_id
        JOIN users u ON t.created_by = u.user_id
        WHERE t.test_case_id = %s
    """, (test_case_id,))
    testcase = cursor.fetchone()

    if not testcase:
        flash("Test case not found.", "error")
        return redirect('/projects')

    # Get test steps
    cursor.execute("SELECT * FROM test_steps WHERE test_case_id = %s ORDER BY step_number", (test_case_id,))
    steps = cursor.fetchall()

    # Get feedback
    cursor.execute("""
        SELECT f.comment, f.created_at, u.username
        FROM feedback f
        JOIN users u ON f.user_id = u.user_id
        WHERE f.test_case_id = %s
        ORDER BY f.created_at DESC
    """, (test_case_id,))
    feedbacks = cursor.fetchall()

    # ✅ Log the download
    cursor.execute("""
        INSERT INTO download_logs (user_id, test_case_id)
        VALUES (%s, %s)
    """, (session['user_id'], test_case_id))

    conn.commit()
    cursor.close()
    conn.close()

    # ✅ Render HTML with timestamp for PDF
    rendered = render_template(
        'testcase_detail_pdf.html',
        testcase=testcase,
        steps=steps,
        feedbacks=feedbacks,
        now=datetime.now()  # 👈 pass timestamp to template
    )
    pdf = pdfkit.from_string(rendered, False)

    filename = f"{testcase['project_title'].replace(' ', '_')}_{testcase['title'].replace(' ', '_')}.pdf"
    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename={filename}'
    return response
