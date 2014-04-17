import sqlite3
import sys
import bcrypt

conn = sqlite3.connect('db.sqlite3')

for line in sys.stdin:
   if '|' not in line:
      break
   user, pw = line.strip().split('|')
   hashed = bcrypt.hashpw(pw, bcrypt.gensalt())
   conn.execute('INSERT INTO users (id, username, password, download) VALUES (NULL, ?, ?, 1)', (user, hashed))

conn.commit()

