import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv('FLASK_SECRET_KEY', 'dev-fallback-key')
    DEBUG = os.getenv('FLASK_DEBUG', 'False') == 'True'

    # MySQL
    MYSQL_HOST = os.getenv('MYSQL_HOST', 'localhost')
    MYSQL_USER = os.getenv('MYSQL_USER', 'root')
    MYSQL_PASSWORD = os.getenv('MYSQL_PASSWORD', '')
    MYSQL_DB = os.getenv('MYSQL_DB', 'support_ticket_db')
    MYSQL_CURSORCLASS = 'DictCursor'

    # OpenAI
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')

    # SMTP
    SMTP_EMAIL = os.getenv('SMTP_EMAIL', '')
    SMTP_PASSWORD = os.getenv('SMTP_PASSWORD', '')
    SMTP_HOST = 'smtp.gmail.com'
    SMTP_PORT = 587
