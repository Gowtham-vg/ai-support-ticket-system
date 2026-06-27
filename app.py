from flask import Flask
from flask_mysqldb import MySQL
from config import Config
import ai_service
# Import blueprints
from auth import auth, init_mysql as auth_mysql
from customer import customer, init_mysql as customer_mysql
from agent import agent, init_mysql as agent_mysql
from admin import admin, init_mysql as admin_mysql
app = Flask(__name__)
app.config.from_object(Config)

# Initialize MySQL
mysql = MySQL(app)

# Inject mysql into each blueprint
with app.app_context():
    auth_mysql(mysql)
    customer_mysql(mysql)
    agent_mysql(mysql)
    admin_mysql(mysql)

# Register blueprints
app.register_blueprint(auth)
app.register_blueprint(customer)
app.register_blueprint(agent)
app.register_blueprint(admin)

if __name__ == '__main__':
    app.run(debug=app.config['DEBUG'])
