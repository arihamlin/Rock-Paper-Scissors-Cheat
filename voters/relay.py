#!/usr/bin/env python

import sys
from comm import P2PNetworkRelay
import tornado.log
import logging

tornado.log.enable_pretty_logging()

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print >> sys.stderr, "Usage: %s <port>" % sys.argv[0]
        sys.exit(1)

    port = int(sys.argv[1])
    logging.info("Starting on port %d...", port)
    network = P2PNetworkRelay()
    network.listen(port)
    tornado.ioloop.IOLoop.instance().start()
