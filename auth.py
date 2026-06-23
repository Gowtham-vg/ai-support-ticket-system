from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from flask_mysqldb import MySQL
import bcrypt

auth = Blueprint('auth', __name__)
mysql = None  # injected in app.py


def init_mysql(mysql_instance):
    global mysql
    mysql = mysql_instance


@auth.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('auth.dashboard_redirect'))
    return redirect(url_for('auth.login'))


@auth.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('auth.dashboard_redirect'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()

        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM users WHERE email = %s AND is_active = TRUE", (email,))
        user = cur.fetchone()
        cur.close()

        if user and bcrypt.checkpw(password.encode('utf-8'), user['password_hash'].encode('utf-8')):
            session['user_id'] = user['id']
            session['name'] = user['name']
            session['email'] = user['email']
            session['role'] = user['role']
            return redirect(url_for('auth.dashboard_redirect'))
        else:
            flash('Invalid email or password.', 'danger')

    return render_template('login.html')


@auth.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('auth.dashboard_redirect'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()

        if not name or not email or not password:
            flash('All fields are required.', 'danger')
            return render_template('register.html')

        if len(password) < 8:
            flash('Password must be at least 8 characters.', 'danger')
            return render_template('register.html')

        cur = mysql.connection.cursor()
        cur.execute("SELECT id FROM users WHERE email = %s", (email,))
        existing = cur.fetchone()

        if existing:
            flash('Email already registered.', 'danger')
            cur.close()
            return render_template('register.html')

        hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        cur.execute(
            "INSERT INTO users (name, email, password_hash, role) VALUES (%s, %s, %s, 'customer')",
            (name, email, hashed)
        )
        mysql.connection.commit()
        cur.close()

        flash('Account created! Please login.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('register.html')


@auth.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully.', 'info')
    return redirect(url_for('auth.login'))


@auth.route('/dashboard')
def dashboard_redirect():
    role = session.get('role')
    if role == 'admin':
        return redirect(url_for('admin.dashboard'))
    elif role == 'agent':
        return redirect(url_for('agent.dashboard'))
    elif role == 'customer':
        return redirect(url_for('customer.dashboard'))
    return redirect(url_for('auth.login'))
