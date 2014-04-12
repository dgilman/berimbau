import sqlite3
import pathlib
import datetime
import subprocess
import functools
import datetime

from flask import Flask, g, render_template, jsonify, request, abort, send_file, Response
import bcrypt

from ifbw import bw_rate

from config import Config

def format_ts(unixts):
   return datetime.datetime.fromtimestamp(unixts).strftime('%m/%d/%y %I:%M:%S %p')

for name, obj in Config.roots:
   p = pathlib.Path(obj.root)
   if not p.exists():
      raise Exception("Path {0} not found, fix your config".format(path.root))
   obj.root = p.resolve()
   obj.kw = name

app = Flask(__name__)

#@app.errorhandler(sqlite3.OperationalError)
#def foo(e):
#   return Response('you hit a locking error with sqlite3, try again')

def login_page():
   return Response('Please log in', 401, {'WWW-Authenticate': 'Basic realm="dsfareg"'})

def login_required(fn):
   @functools.wraps(fn)
   def decorated(*args, **kwargs):
      auth = request.authorization
      if not auth:
         return login_page()
      rval = g
      g.c.execute('SELECT id, password, is_admin FROM users WHERE username = ?', (auth.username,))
      rval = g.c.fetchall()
      if not rval:
         return login_page()
      uid, password_hash, is_admin = rval[0]
      if bcrypt.hashpw(auth.password, password_hash):
         g.user = {"uid": uid, "username": auth.username, "is_admin": is_admin}
         return fn(*args, **kwargs)
      else:
         return login_page()
   return decorated

@app.before_request
def before_request():
   g.conn = sqlite3.connect(Config.db_dsn, detect_types=sqlite3.PARSE_DECLTYPES)
   g.c = g.conn.cursor()
   g.user = None

@app.teardown_request
def after_request(response_class):
   g.conn.commit()
   g.c.close()
   g.conn.close()

@app.context_processor
def add_globals():
   return {'Config': Config,
           'format_ts': format_ts}

@app.route('/')
@login_required
def index_page():
   return render_template('index.html')

@app.route('/fs/<string:root>')
@login_required
def fs_page(root):
   if root not in [x[0] for x in Config.roots]:
      abort(404)
   root = [x[1] for x in Config.roots if x[0] == root][0]
   if 'path' not in request.args:
      path = root.root
   else:
      path = root.root / request.args['path']
      try:
         path = path.resolve()
      except FileNotFoundError:
         # give a consistent error as to not leak filesystem contents
         abort(403)
      if root.root == path:
         pass
      elif root.root not in path.parents:
         abort(403)

   if not g.user['is_admin']:
      g.c.execute('INSERT INTO logs (id, user, root, ts, path) VALUES (NULL, ?, ?, ?, ?)',
         (g.user['uid'], root.rid, datetime.datetime.utcnow(), path.as_posix()))

   if path.is_file():
      return send_file(path.as_posix())
   return render_template('fs.html', root=root, path=path)

@app.route('/changelog')
@login_required
def changelog_page():
   GIT_COMMIT_FIELDS = ['id', 'author_name', 'author_email', 'date', 'subject', 'body']
   GIT_LOG_FORMAT = ['%h', '%an', '%ae', '%ad', '%s', '%b']
   GIT_LOG_FORMAT = '%x1f'.join(GIT_LOG_FORMAT) + '%x1e'
   rval = subprocess.check_output(['git', 'log', '--format={0}'.format(GIT_LOG_FORMAT)])
   rval = rval.decode().strip('\n\x1e').split("\x1e")
   log = [row.strip().split("\x1f") for row in rval]
   log = [dict(zip(GIT_COMMIT_FIELDS, row)) for row in log if row]
   return render_template('changelog.html', log=log)

@app.route('/bw')
@login_required
def bw_page():
   ikb_s, okb_s = bw_rate(Config.iface)
   return jsonify(okb_s=round(okb_s, 2))

@app.route('/user', methods=('GET', 'POST'))
@login_required
def user_page():
   if request.method == 'POST':
      new_hash = bcrypt.hashpw(request.form['user-password'], bcrypt.gensalt())
      g.c.execute('UPDATE users SET password = ?, email = ? WHERE id = ?',
         (new_hash, request.form['user-email'], g.user['uid']))
      return render_template('user.html', email=request.form['user-email'])
   g.c.execute('SELECT email FROM users WHERE id = ?', (g.user['uid'],))
   email = g.c.fetchall()
   if email:
      email = email[0][0]
   else:
      email = ''
   return render_template('user.html', email=email)

if __name__ == '__main__':
   app.secret_key = b'\x12\xef\xdd\x93\xc8\xf6\xa5\xe0\x90\xfam\x9f\x92\xc0\x18\xa4KvP\x9cV/\xfa\xb1l,\x94\x11\x96a'
   app.run(host='0.0.0.0', threaded=True, debug=True)
