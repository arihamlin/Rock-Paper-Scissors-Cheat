#!/usr/bin/env python

import sys
from comm import P2PNetworkRelay, VoterInterfaceProxy
import tornado.log
import logging
import tornado.web


tornado.log.enable_pretty_logging()

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print >> sys.stderr, "Usage: %s <relay port> <interface port>" % sys.argv[0]
        sys.exit(1)

    relay_port = int(sys.argv[1])
    interface_port = int(sys.argv[2])
    logging.info("Starting relay on port %d...", relay_port)
    logging.info("Starting interface on port %d...", interface_port)

    network = P2PNetworkRelay()
    app = tornado.web.Application([
             (r"/", VoterInterfaceProxy, dict(relay=network)),
        ])
    app.listen(interface_port)
    network.listen(relay_port)
    tornado.ioloop.IOLoop.instance().start()
