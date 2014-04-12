import sys
import os
sys.path.append(os.path.dirname(__file__))
sys.prefix = os.path.dirname(os.path.abspath(__file__))

from config import Config

import site
site.addsitedir(Config.site_dir)

from berimbau import app as application

application.use_x_sendfile = True
