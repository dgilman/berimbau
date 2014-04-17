import sqlite3
import pathlib
import datetime
import subprocess
import functools
import itertools
import datetime
import threading
import heapq
import os

from flask import Flask, g, render_template, jsonify, request, abort, send_file, Response
import bcrypt
import fsevents

from ifbw import bw_rate

from config import Config

def format_ts(unixts):
   return datetime.datetime.fromtimestamp(unixts).strftime('%m/%d/%y %I:%M:%S %p')

Config.root_map = {}
for name, obj in Config.roots:
   p = pathlib.Path(obj.root)
   if not p.exists():
      raise Exception("Path {0} not found, fix your config".format(path.root))
   obj.root = p.resolve()
   obj.kw = name
   Config.root_map[obj.rid] = name

top_50 = []
top_50_lock = threading.Lock()

def fsevents_callback(*args, **kwargs):
   global top_50
   event = args[0]
   if event.mask & fsevents.IN_CREATE|fsevents.IN_MOVED_FROM:
      if os.path.basename(event.name)[0] == '.':
         return
      if not os.path.exists(event.name):
         with top_50_lock:
            if event.name in top_50:
               top_50.remove(event.name)
         return
      candidate = pathlib.Path(event.name).resolve()
      root_name = None
      root_path = None
      for root, obj in [(x[0], x[1].root) for x in Config.roots]:
         if obj in candidate.parents:
            root_name, root_path = root, obj
      if not root_name:
         return
      with top_50_lock:
         top_50 = heapq.nlargest(30, itertools.chain(top_50,
            ((root_name, candidate.as_posix(), candidate.stat().st_birthtime),),),
            lambda x: x[2])

obs = fsevents.Observer()
for root, obj in Config.roots:
   stream = fsevents.Stream(fsevents_callback, obj.root.as_posix(), file_events=True)
   obs.schedule(stream)
obs.start()

def search_dirs(dirs):
   for root, directory in dirs:
      for dirpath, dirnames, filenames in os.walk(directory):
         for filename in filenames:
            if filename[0] == '.':
               continue
            path = os.path.join(dirpath, filename)
            yield root, path, os.stat(path).st_birthtime

with top_50_lock:
   top_50 = heapq.nlargest(30,
      search_dirs([(x[0], x[1].root.as_posix()) for x in Config.roots]),
      lambda x: x[2])


app = Flask(__name__)

@app.errorhandler(sqlite3.OperationalError)
def foo(e):
   return Response('you hit a locking error with sqlite3, try again', 500)

def login_page():
   return Response('Please log in', 401, {'WWW-Authenticate': 'Basic realm="dsfareg"'})

def login_required(fn):
   @functools.wraps(fn)
   def decorated(*args, **kwargs):
      auth = request.authorization
      if not auth:
         return login_page()
      rval = g
      g.c.execute('SELECT id, password, is_admin, download FROM users WHERE username = ?', (auth.username,))
      rval = g.c.fetchall()
      if not rval:
         return login_page()
      uid, password_hash, is_admin, download = rval[0]
      if bcrypt.hashpw(auth.password, password_hash):
         g.user = {"uid": uid, "username": auth.username, "is_admin": is_admin}
         if download:
            g.user['download'] = True
         else:
            g.user['download'] = False
         return fn(*args, **kwargs)
      else:
         return login_page()
   return decorated

def admin_required(fn):
   @functools.wraps(fn)
   def decorated(*args, **kwargs):
      if not g.user['is_admin']:
         abort(403)
      return fn(*args, **kwargs)
   return decorated

@app.before_request
def before_request():
   g.conn = sqlite3.connect(Config.db_dsn, isolation_level=None,
      detect_types=sqlite3.PARSE_DECLTYPES)
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
   with top_50_lock:
      return render_template('index.html', top_50=top_50)

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

   g.c.execute('INSERT INTO logs (id, user, root, ts, path) VALUES (NULL, ?, ?, ?, ?)',
      (g.user['uid'], root.rid, datetime.datetime.utcnow(), path.as_posix()))

   if path.is_file():
      return send_file(path.as_posix(), as_attachment=g.user["download"])
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
      var = request.form.getlist('user-download')
      if var and var[0] == 'on':
         download = True
      else:
         download = False
      g.c.execute('UPDATE users SET password = ?, email = ?, download = ? WHERE id = ?',
         (new_hash, request.form['user-email'], download, g.user['uid']))
      return render_template('user.html', email=request.form['user-email'],
         download=download)
   g.c.execute('SELECT email, download FROM users WHERE id = ?', (g.user['uid'],))
   email, download = g.c.fetchall()[0]
   if not email:
      email = ''
   return render_template('user.html', email=email, download=download)

@app.route('/oversight')
@login_required
@admin_required
def oversight_page():
   g.c.execute('SELECT id, username, email, is_admin FROM users')
   users = g.c.fetchall()
   return render_template('oversight.html', users=users)

@app.route('/user_log/<int:uid>/', defaults={'page': 1})
@app.route('/user_log/<int:uid>/<int:page>')
@login_required
@admin_required
def user_log_page(uid, page):
   g.c.execute('select username, email from users where id = ?', (uid,))
   user_info = g.c.fetchall()
   if not user_info:
      abort(404)
   name_string = '{0} <{1}>'.format(user_info[0][0], user_info[0][1])
   g.c.execute('select * from logs where user = ? order by ts desc limit 20 offset ?',
      (uid, (page-1)*20))
   logs = g.c.fetchall()
   return render_template('user_log.html', user_info=name_string,
      logs=logs, next_page=page+1, uid=uid)

if __name__ == '__main__':
   app.secret_key = b'\x12\xef\xdd\x93\xc8\xf6\xa5\xe0\x90\xfam\x9f\x92\xc0\x18\xa4KvP\x9cV/\xfa\xb1l,\x94\x11\x96a'
   app.run(host='0.0.0.0', threaded=True, debug=True)
