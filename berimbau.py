import sqlite3
import pathlib
import datetime

from flask import Flask, g, render_template, jsonify, request, abort, send_file

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

@app.before_request
def before_request():
   g.conn = sqlite3.connect(Config.db_dsn, detect_types=sqlite3.PARSE_DECLTYPES)
   g.c = g.conn.cursor()

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
def index_page():
   return render_template('index.html')

@app.route('/fs/<string:root>')
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
   if path.is_file():
      return send_file(path.as_posix())
   return render_template('fs.html', root=root, path=path)

if __name__ == '__main__':
   app.run(host='0.0.0.0', threaded=True, debug=True)
