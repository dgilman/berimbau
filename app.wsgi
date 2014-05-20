import sys
import os
sys.path.append(os.path.dirname(__file__))
sys.prefix = os.path.dirname(os.path.abspath(__file__))

from config import Config

import site
site.addsitedir(Config.site_dir)

from berimbau import app as application

application.secret_key = b'\xf4\x95Uq\xc5\xce4`\xd6\xd2#`\x98S,v\xe2\xf42\x08\x8c\xcd\x00m\x92\xc0\xcf\x8eJ\xb3'
#application.use_x_sendfile = True
