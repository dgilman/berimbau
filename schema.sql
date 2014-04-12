CREATE TABLE users (
   id integer primary key,
   username TEXT UNIQUE,
   password BLOB,
   email TEXT,
   is_admin BOOLEAN
   );

CREATE TABLE taglines (
   id INTEGER PRIMARY KEY,
   user INTEGER REFERENCES users(id),
   tagline TEXT
   );

CREATE TABLE logs (
   id INTEGER PRIMARY KEY,
   user INTEGER REFERENCES users(id),
   root INTEGER,
   ts timestamp,
   path TEXT
   );

CREATE INDEX logs_user ON logs (user, ts);
