from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from flask_mysqldb import MySQL
from decorators import role_required
from ai_service import classify_ticket
from email_service import notify_ticket_created, notify_ticket_replied

customer = Blueprint('customer', __name__, url_prefix='/customer')
mysql = None


def init_mysql(mysql_instance):
    global mysql
    mysql = mysql_instance


@customer.route('/dashboard')
@role_required('customer')
def dashboard():
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT t.*, 
               (SELECT COUNT(*) FROM responses r WHERE r.ticket_id = t.id AND r.is_internal_note = FALSE) as reply_count
        FROM tickets t
        WHERE t.customer_id = %s
        ORDER BY t.created_at DESC
    """, (session['user_id'],))
    tickets = cur.fetchall()
    cur.close()

    # Count by status for summary cards
    stats = {'open': 0, 'in_progress': 0, 'resolved': 0, 'closed': 0}
    for t in tickets:
        stats[t['status']] = stats.get(t['status'], 0) + 1

    return render_template('customer_dashboard.html',
                       tickets=tickets,
                       stats=stats)


@customer.route('/ticket/create', methods=['GET', 'POST'])
@role_required('customer')
def create_ticket():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()

        if not title or not description:
            flash('Title and description are required.', 'danger')
            return render_template('create_ticket.html')

        # Generate ticket number
        cur = mysql.connection.cursor()
        cur.execute("SELECT COUNT(*) as total FROM tickets")
        count = cur.fetchone()['total']
        ticket_number = f"TKT-{str(count + 1).zfill(5)}"

        # AI classify
        ai_result = classify_ticket(title, description)
        print("AI RESULT =", ai_result)

        cur.execute("""
            INSERT INTO tickets 
            (ticket_number, title, description, category, priority, customer_id, 
             ai_suggested_category, ai_suggested_priority)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            ticket_number, title, description,
            ai_result['category'], ai_result['priority'],
            session['user_id'],
            ai_result['category'], ai_result['priority']
        ))
        ticket_id = cur.lastrowid

        # Log AI usage
        cur.execute("""
            INSERT INTO ai_logs (ticket_id, action, prompt_tokens, completion_tokens, ai_output)
            VALUES (%s, 'classify', %s, %s, %s)
        """, (ticket_id, ai_result['prompt_tokens'], ai_result['completion_tokens'],
              f"category={ai_result['category']}, priority={ai_result['priority']}"))

        cur.execute("""
            INSERT INTO ticket_activity(ticket_id, action)
        VALUES(%s, %s)
    """, (
    ticket_id,
    "Ticket created"
))
        mysql.connection.commit()

        # Send email notification
        notify_ticket_created(session['email'], session['name'], ticket_number, title)

        flash(f'Ticket {ticket_number} created successfully!', 'success')
        return redirect(url_for('customer.dashboard'))

    return render_template('create_ticket.html')


@customer.route('/ticket/<int:ticket_id>', methods=['GET', 'POST'])
@role_required('customer')
def view_ticket(ticket_id):
    cur = mysql.connection.cursor()

    try:
        # Verify this ticket belongs to the logged-in customer
        cur.execute("""
            SELECT
                t.*,
                c.name AS customer_name,
                c.email AS customer_email,
                a.name AS agent_name
            FROM tickets t
            JOIN users c
                ON c.id = t.customer_id
            LEFT JOIN users a
                ON a.id = t.assigned_agent_id
            WHERE t.id = %s
            AND t.customer_id = %s
        """, (ticket_id, session['user_id']))

        ticket = cur.fetchone()

        if not ticket:
            flash('Ticket not found.', 'danger')
            return redirect(url_for('customer.dashboard'))

        # Customer reply
        if request.method == "POST":

            message = request.form.get("message", "").strip()

            if not message:
                flash("Reply cannot be empty.", "danger")

            else:
                cur.execute("""
                    INSERT INTO responses
                    (ticket_id, responder_id, message, is_internal_note)
                    VALUES (%s, %s, %s, FALSE)
                """, (
                    ticket_id,
                    session['user_id'],
                    message
                ))

                cur.execute("""
                    INSERT INTO ticket_activity(ticket_id, action)
                    VALUES (%s, %s)
                """, (
                    ticket_id,
                    "Customer replied"
                ))

                mysql.connection.commit()

                notify_ticket_replied(
                    ticket['customer_email'],
                    ticket['customer_name'],
                    ticket['ticket_number'],
                    ticket['title'],
                    message
                )

                flash("Reply sent successfully.", "success")

                return redirect(
                    url_for(
                        'customer.view_ticket',
                        ticket_id=ticket_id
                    )
                )

        # Get responses
        cur.execute("""
            SELECT r.*, u.name AS responder_name, u.role AS responder_role
            FROM responses r
            JOIN users u ON u.id = r.responder_id
            WHERE r.ticket_id = %s
            AND r.is_internal_note = FALSE
            ORDER BY r.created_at ASC
        """, (ticket_id,))
        responses = cur.fetchall()

        # Get timeline
        cur.execute("""
            SELECT action, created_at
            FROM ticket_activity
            WHERE ticket_id = %s
            ORDER BY created_at DESC
        """, (ticket_id,))
        timeline = cur.fetchall()

        return render_template(
            'ticket_detail.html',
            ticket=ticket,
            responses=responses,
            timeline=timeline
        )

    finally:
        cur.close()
