import bcrypt, os
from dotenv import load_dotenv
load_dotenv()
import MySQLdb

pwd = b'Admin@123'
hashed = bcrypt.hashpw(pwd, bcrypt.gensalt()).decode('utf-8')

db = MySQLdb.connect(
    host=os.getenv('MYSQL_HOST'),
    user=os.getenv('MYSQL_USER'),
    passwd=os.getenv('MYSQL_PASSWORD'),
    db=os.getenv('MYSQL_DB')
)
cur = db.cursor()
cur.execute("UPDATE users SET password_hash=%s WHERE email='admin@support.com'", (hashed,))
db.commit()
print('Done! Login: admin@support.com / Admin@123')