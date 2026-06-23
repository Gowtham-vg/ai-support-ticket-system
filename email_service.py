import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


def send_email(to_email: str, subject: str, body_html: str) -> bool:
    smtp_email = os.getenv('SMTP_EMAIL', '')
    smtp_password = os.getenv('SMTP_PASSWORD', '')

    if not smtp_email or not smtp_password:
        print("[Email] SMTP credentials not configured.")
        return False

    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = smtp_email
        msg['To'] = to_email
        msg.attach(MIMEText(body_html, 'html'))

        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(smtp_email, smtp_password)
            server.sendmail(smtp_email, to_email, msg.as_string())

        return True

    except Exception as e:
        print(f"[Email error] {e}")
        return False


def notify_ticket_created(customer_email: str, customer_name: str, ticket_number: str, title: str):
    subject = f"Ticket {ticket_number} Created - {title}"
    body_html = f"""
    <h3>New Reply Received</h3>

    <p>Hi {customer_name},</p>

    <p>
    A support agent has replied to your ticket
    <b>{ticket_number}</b>.
    </p>

    <p><strong>Agent Reply:</strong></p>

    <div style="padding:12px;border-left:4px solid #0d6efd;background:#f8f9fa;">
    
    </div>

    <br>

    <p>
    Please login to your account for further updates.
    </p>

    <p>
    Support Team
    </p>
    """
    return send_email(customer_email, subject, body_html)


def notify_ticket_replied(
    customer_email,
    customer_name,
    ticket_number,
    ticket_title,
    reply_message=""
):
    subject = f"New Reply on {ticket_number} - {ticket_title}"
    body_html = f"""
    <h3>Ticket Created Successfully</h3>
    <p>Hi {customer_name},</p>
    <p>
    A support agent can replied to your ticket <strong>{ticket_number} - {ticket_title}</strong>.
    </p>
    <p><strong>Agent Reply:</strong></p>
    <div style="padding:12px;border-left:4px solid #0d6efd;background:#f8f9fa;">
    {reply_message}
    </div>
    <br>
    <p>Please login to your account for further updates.</p>
    <p>Support Team</p>
    """
    return send_email(customer_email, subject, body_html)


def notify_ticket_resolved(customer_email: str, customer_name: str, ticket_number: str, title: str):
    subject = f"Ticket {ticket_number} Resolved"
    body = f"""
    <h3>Hi {customer_name},</h3>
    <p>Your ticket <strong>{ticket_number} - {title}</strong> has been marked as resolved.</p>
    <p>If your issue persists, you can reopen the ticket from your dashboard.</p>
    <br><p>Support Team</p>
    """
    return send_email(customer_email, subject, body)
