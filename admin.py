from flask import Blueprint, render_template, request, redirect, url_for, session, flash, make_response
from flask_mysqldb import MySQL
from decorators import role_required
from pdf_service import generate_report_pdf
import bcrypt

admin = Blueprint('admin', __name__, url_prefix='/admin')
mysql = None


def init_mysql(mysql_instance):
    global mysql
    mysql = mysql_instance


@admin.route('/dashboard')
@role_required('admin')
def dashboard():
    cur = mysql.connection.cursor()

    # Overall ticket stats
    cur.execute("""
        SELECT 
            COUNT(*) as total,
            SUM(status = 'open') as open_count,
            SUM(status = 'in_progress') as in_progress_count,
            SUM(status = 'resolved') as resolved_count,
            SUM(status = 'closed') as closed_count
        FROM tickets
    """)
    ticket_stats = cur.fetchone()

    # Tickets by category (for Chart.js)
    cur.execute("""
        SELECT category, COUNT(*) as count
        FROM tickets GROUP BY category
    """)
    by_category = cur.fetchall()

    # Tickets by priority (for Chart.js)
    cur.execute("""
        SELECT priority, COUNT(*) as count
        FROM tickets GROUP BY priority
    """)
    by_priority = cur.fetchall()

    # Tickets created per day (last 14 days)
    cur.execute("""
        SELECT DATE(created_at) as date, COUNT(*) as count
        FROM tickets
        WHERE created_at >= DATE_SUB(NOW(), INTERVAL 14 DAY)
        GROUP BY DATE(created_at)
        ORDER BY date ASC
    """)
    daily_trend = cur.fetchall()

    # Agent performance
    cur.execute("""
        SELECT u.name, 
               COUNT(t.id) as assigned,
               SUM(t.status = 'resolved') as resolved,
               SUM(t.status = 'in_progress') as in_progress
        FROM users u
        LEFT JOIN tickets t ON t.assigned_agent_id = u.id
        WHERE u.role = 'agent'
        GROUP BY u.id, u.name
    """)
    agent_stats = cur.fetchall()

    # AI usage stats
    cur.execute("""
        SELECT action, COUNT(*) as count, 
               SUM(prompt_tokens + completion_tokens) as total_tokens
        FROM ai_logs GROUP BY action
    """)
    ai_stats = cur.fetchall()

    # Recent tickets
    cur.execute("""
        SELECT t.*, u.name as customer_name, a.name as agent_name
        FROM tickets t
        JOIN users u ON u.id = t.customer_id
        LEFT JOIN users a ON a.id = t.assigned_agent_id
        ORDER BY t.created_at DESC LIMIT 10
    """)
    recent_tickets = cur.fetchall()

    cur.close()

    stats = {
    'open': ticket_stats['open_count'] or 0,
    'in_progress': ticket_stats['in_progress_count'] or 0,
    'resolved': ticket_stats['resolved_count'] or 0,
    'closed': ticket_stats['closed_count'] or 0
}

    return render_template(
    'admin_dashboard.html',
    stats=stats,
    tickets=recent_tickets
)


@admin.route('/users')
@role_required('admin')
def users():
    cur = mysql.connection.cursor()
    cur.execute("SELECT id, name, email, role, is_active, created_at FROM users ORDER BY created_at DESC")
    all_users = cur.fetchall()
    cur.close()

    return render_template('users.html', users=all_users)


@admin.route('/users/add', methods=['POST'])
@role_required('admin')
def add_user():
    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '').strip()
    role = request.form.get('role', 'customer')

    if role not in ['customer', 'agent', 'admin']:
        flash('Invalid role.', 'danger')
        return redirect(url_for('admin.users'))

    cur = mysql.connection.cursor()
    cur.execute("SELECT id FROM users WHERE email = %s", (email,))
    if cur.fetchone():
        flash('Email already exists.', 'danger')
        cur.close()
        return redirect(url_for('admin.users'))

    hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    cur.execute(
        "INSERT INTO users (name, email, password_hash, role) VALUES (%s, %s, %s, %s)",
        (name, email, hashed, role)
    )
    mysql.connection.commit()
    cur.close()
    flash(f'{role.capitalize()} account created.', 'success')
    return redirect(url_for('admin.users'))


@admin.route('/users/<int:user_id>/toggle', methods=['POST'])
@role_required('admin')
def toggle_user(user_id):
    if user_id == session['user_id']:
        flash("Can't deactivate your own account.", 'danger')
        return redirect(url_for('admin.users'))

    cur = mysql.connection.cursor()
    cur.execute("UPDATE users SET is_active = NOT is_active WHERE id = %s", (user_id,))
    mysql.connection.commit()
    cur.close()
    flash('User status updated.', 'success')
    return redirect(url_for('admin.users'))


@admin.route('/tickets')
@role_required('admin')
def all_tickets():
    status_filter = request.args.get('status', '')
    priority_filter = request.args.get('priority', '')

    query = """
        SELECT t.*, u.name as customer_name, a.name as agent_name
        FROM tickets t
        JOIN users u ON u.id = t.customer_id
        LEFT JOIN users a ON a.id = t.assigned_agent_id
        WHERE 1=1
    """
    params = []

    if status_filter:
        query += " AND t.status = %s"
        params.append(status_filter)
    if priority_filter:
        query += " AND t.priority = %s"
        params.append(priority_filter)

    query += " ORDER BY t.created_at DESC"

    cur = mysql.connection.cursor()
    cur.execute(query, params)
    tickets = cur.fetchall()

    # Get agents list for reassignment
    cur.execute("SELECT id, name FROM users WHERE role = 'agent' AND is_active = TRUE")
    agents = cur.fetchall()
    cur.close()

    return render_template('tickets.html',
                           tickets=tickets,
                           agents=agents,
                           status_filter=status_filter,
                           priority_filter=priority_filter)


@admin.route('/tickets/<int:ticket_id>/assign', methods=['POST'])
@role_required('admin')
def assign_ticket(ticket_id):
    agent_id = request.form.get('agent_id')
    cur = mysql.connection.cursor()
    cur.execute("""
        UPDATE tickets SET assigned_agent_id = %s, status = 'in_progress'
        WHERE id = %s
    """, (agent_id, ticket_id))
    mysql.connection.commit()
    cur.close()
    flash('Ticket assigned.', 'success')
    return redirect(url_for('admin.all_tickets'))


@admin.route('/report/download')
@role_required('admin')
def download_report():
    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT t.ticket_number, t.title, t.category, t.priority, t.status,
               u.name as customer, a.name as agent,
               t.created_at, t.resolved_at
        FROM tickets t
        JOIN users u ON u.id = t.customer_id
        LEFT JOIN users a ON a.id = t.assigned_agent_id
        ORDER BY t.created_at DESC
    """)
    tickets = cur.fetchall()

    cur.execute("""
        SELECT COUNT(*) as total,
               SUM(status='resolved') as resolved,
               SUM(status='open') as open_t,
               SUM(status='in_progress') as in_progress
        FROM tickets
    """)
    summary = cur.fetchone()
    cur.close()

    pdf_bytes = generate_report_pdf(tickets, summary)

    response = make_response(pdf_bytes)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = 'attachment; filename=ticket_report.pdf'
    return response
