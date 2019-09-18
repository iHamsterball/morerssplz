#!/usr/bin/python
# -*- coding: utf-8 -*-

import tornado.web
import os
import sys

from morerss import *
from tornado.httpserver import HTTPServer
from tornado.options import define, options

topdir = os.path.dirname(os.path.abspath(__file__))

# tmpl_dir = os.path.join(topdir, 'tmpl')
static_dir = os.path.join(topdir, 'static')


routers = [
    # (r'/static/(.*)', tornado.web.StaticFileHandler, {'path': static_dir}),
    (r'/zhihuzhuanlan/([^/]+)', ZhihuZhuanlanHandler),
    (r'/zhihu/([^/]+)', ZhihuStream),
    (r'/static_zhihu/(\d+)', StaticZhihuHandler),
    (r'/v2ex/(\d+)', V2exCommentHandler),
]


def main():
    define("port", default=8000, help="run on the given port", type=int)
    define("address", default='', help="run on the given address", type=str)
    define("debug", default=False, help="debug mode", type=bool)
    define("zhihu-proxy", default=False,
           help="use proxies for zhihu", type=bool)

    tornado.options.parse_command_line()
    application = tornado.web.Application(
        routers,
        gzip=True,
        debug=options.debug,
        # template_path = tmpl_dir,
        # cookie_secret = settings['cookie_secret'],
    )
    http_server = HTTPServer(application, xheaders=True)
    http_server.listen(options.port, address=options.address)
    tornado.ioloop.IOLoop.instance().start()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
