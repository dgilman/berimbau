class TorrentRoot(object):
   root = '/Volumes/ntfs/Torrents'
   name = 'Torrents'
   desc = 'Torrent downloads'

class MusicRoot(object):
   root = '/Volumes/ntfs/Music/Music'
   name = 'Music'
   desc = 'David\'s iTunes library'

class MoviesRoot(object):
   root = '/Volumes/ntfs/Movies'
   name = 'Movies'
   desc = 'Movies'

class OldTorrentRoot(object):
   root = '/Volumes/ntfs/old_torrent'
   name = 'dorm.servehttp.com'
   desc = 'the old dorm.servehttp.com server contents'

class TVRoot(object):
   root = '/Volumes/ntfs/TV'
   name = 'TV'
   desc = 'Television'

class FappanRoot(object):
   root = '/Volumes/ntfs/fap'
   name = 'Fappan'
   desc = 'But I poop from there!'

class Config(object):
   db_dsn = 'db.sqlite3'
   roots = (('tv', TVRoot),
            ('torrents', TorrentRoot),
            ('music', MusicRoot),
            ('movies', MoviesRoot),
            ('dorm.servehttp.com', OldTorrentRoot),
            ('fap', FappanRoot)
   )
