from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from flask_mysqldb import MySQL
from decorators import role_required
from ai_service import generate_draft_response
from email_service import notify_ticket_replied, notify_ticket_resolved

agent = Blueprint('agent', __name__, url_prefix='/agent')
mysql = None


def init_mysql(mysql_instance):
    global mysql
    mysql = mysql_instance


# ---------------- DASHBOARD ----------------
@agent.route('/dashboard')
@role_required('agent')
def dashboard():
    cur = mysql.connection.cursor()
    try:
        cur.execute("""
            SELECT t.*, u.name as customer_name,
                   (SELECT COUNT(*) FROM responses r 
                    WHERE r.ticket_id = t.id AND r.is_internal_note = FALSE) as reply_count
            FROM tickets t
            JOIN users u ON u.id = t.customer_id
            WHERE t.assigned_agent_id = %s
            ORDER BY FIELD(t.priority, 'urgent', 'high', 'medium', 'low'),
                     t.created_at ASC
        """, (session['user_id'],))
        my_tickets = cur.fetchall()

        cur.execute("""
            SELECT t.*, u.name as customer_name
            FROM tickets t
            JOIN users u ON u.id = t.customer_id
            WHERE t.assigned_agent_id IS NULL
            AND t.status = 'open'
            ORDER BY FIELD(t.priority, 'urgent', 'high', 'medium', 'low'),
                     t.created_at ASC
        """)
        unassigned = cur.fetchall()

        stats = {'open': 0, 'in_progress': 0, 'resolved': 0}

        for t in my_tickets:
            if t['status'] in stats:
                stats[t['status']] += 1

        return render_template(
            'agent_dashboard.html',
            tickets=my_tickets,
            my_tickets=my_tickets,
            unassigned=unassigned,
            stats=stats
        )

    finally:
        cur.close()


# ---------------- VIEW TICKET ----------------
@agent.route('/ticket/<int:ticket_id>', methods=['GET', 'POST'])
@role_required('agent')
def view_ticket(ticket_id):
    cur = mysql.connection.cursor()

    try:
        # GET TICKET
        cur.execute("""
            SELECT t.*,
                   u.name as customer_name,
                   u.email as customer_email,
                   a.name as agent_name
            FROM tickets t
            JOIN users u ON u.id = t.customer_id
            LEFT JOIN users a ON a.id = t.assigned_agent_id
            WHERE t.id = %s
        """, (ticket_id,))
        ticket = cur.fetchone()

        if not ticket:
            flash('Ticket not found.', 'danger')
            return redirect(url_for('agent.dashboard'))

        # ---------------- POST ACTIONS ----------------
        if request.method == 'POST':
            action = request.form.get('action')

            # -------- REPLY --------
            if action == 'reply':
                message = request.form.get('message', '').strip()
                is_internal = request.form.get('is_internal', 'false') == 'true'

                if not message:
                    flash('Reply cannot be empty.', 'danger')
                else:
                    cur.execute("""
                        INSERT INTO responses 
                        (ticket_id, responder_id, message, is_internal_note)
                        VALUES (%s, %s, %s, %s)
                    """, (ticket_id, session['user_id'], message, is_internal))

                    if not ticket['assigned_agent_id']:
                        cur.execute("""
                            UPDATE tickets 
                            SET assigned_agent_id = %s, status = 'in_progress'
                            WHERE id = %s
                        """, (session['user_id'], ticket_id))

                    cur.execute("""
                        INSERT INTO ticket_activity(ticket_id, action)
                        VALUES (%s, %s)
                    """, (
                        ticket_id,
                        "Agent replied" if not is_internal else "Internal note added"
                    ))

                    mysql.connection.commit()

                    if not is_internal:
                        notify_ticket_replied(
                            ticket['customer_email'],
                            ticket['customer_name'],
                            ticket['ticket_number'],
                            ticket['title'],
                            message
                        )
                        flash('Reply sent.', 'success')
                    else:
                        flash('Internal note saved.', 'info')

            # -------- UPDATE STATUS --------
            elif action == 'update_status':
                new_status = request.form.get('status')
                valid = ['open', 'in_progress', 'resolved', 'closed']

                if new_status in valid:
                    resolved_at = "NOW()" if new_status == 'resolved' else "NULL"

                    cur.execute(f"""
                        UPDATE tickets 
                        SET status = %s, resolved_at = {resolved_at}
                        WHERE id = %s
                    """, (new_status, ticket_id))

                    cur.execute("""
                        INSERT INTO ticket_activity(ticket_id, action)
                        VALUES (%s, %s)
                    """, (
                        ticket_id,
                        f"Status changed to {new_status.replace('_', ' ').title()}"
                    ))

                    mysql.connection.commit()

                    if new_status == 'resolved':
                        notify_ticket_resolved(
                            ticket['customer_email'],
                            ticket['customer_name'],
                            ticket['ticket_number'],
                            ticket['title']
                        )

                    flash(f'Status updated to {new_status}.', 'success')

            # -------- ASSIGN SELF --------
            elif action == 'assign_self':
                cur.execute("""
                    UPDATE tickets 
                    SET assigned_agent_id = %s, status = 'in_progress'
                    WHERE id = %s
                """, (session['user_id'], ticket_id))

                cur.execute("""
                    INSERT INTO ticket_activity(ticket_id, action)
                    VALUES (%s, %s)
                """, (
                    ticket_id,
                    f"Ticket assigned to {session['name']}"
                ))

                mysql.connection.commit()
                flash('Ticket assigned to you.', 'success')

            return redirect(url_for('agent.view_ticket', ticket_id=ticket_id))

        # ---------------- GET DATA ----------------
        cur.execute("""
            SELECT r.*, u.name as responder_name, u.role as responder_role
            FROM responses r
            JOIN users u ON u.id = r.responder_id
            WHERE r.ticket_id = %s
            ORDER BY r.created_at ASC
        """, (ticket_id,))
        responses = cur.fetchall()

        cur.execute("""
            SELECT action, created_at
            FROM ticket_activity
            WHERE ticket_id = %s
            ORDER BY created_at DESC
        """, (ticket_id,))
        timeline = cur.fetchall()

        return render_template(
            'agent_ticket_detail.html',
            ticket=ticket,
            responses=responses,
            timeline=timeline
        )

    finally:
        cur.close()


# ---------------- AI DRAFT ----------------
@agent.route('/ticket/<int:ticket_id>/ai-draft', methods=['POST'])
@role_required('agent')
def get_ai_draft(ticket_id):
    cur = mysql.connection.cursor()

    try:
        cur.execute("SELECT * FROM tickets WHERE id = %s", (ticket_id,))
        ticket = cur.fetchone()

        if not ticket:
            return jsonify({'error': 'Ticket not found'}), 404

        cur.execute("""
            SELECT r.message, u.role
            FROM responses r
            JOIN users u ON u.id = r.responder_id
            WHERE r.ticket_id = %s AND r.is_internal_note = FALSE
            ORDER BY r.created_at ASC
        """, (ticket_id,))
        prev_responses = cur.fetchall()

        result = generate_draft_response(
            ticket['title'],
            ticket['description'],
            prev_responses
        )

        if result['draft']:
            cur.execute("""
                INSERT INTO ai_logs 
                (ticket_id, action, prompt_tokens, completion_tokens, ai_output)
                VALUES (%s, 'draft_response', %s, %s, %s)
            """, (
                ticket_id,
                result['prompt_tokens'],
                result['completion_tokens'],
                result['draft']
            ))
            mysql.connection.commit()

        return jsonify({'draft': result['draft']})

    finally:
        cur.close()