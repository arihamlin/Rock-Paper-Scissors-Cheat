#!/usr/bin/env python

import tornado.log
import tornado.web
import logging
import sys
from comm import VoterNode

tornado.log.enable_pretty_logging()


class Voter(VoterNode):
    def __init__(self, addr):
        VoterNode.__init__(self, addr)

    def on_connect(self):
        pass

    def on_message(self, sender_id, msg):
        pass

    def on_close(self):
        VoterNode.on_close(self)
        # clean up


class VoterInterface(tornado.web.RequestHandler):
    def initialize(self, voter):
        self.voter = voter

    def post(self):
        self.finish({})

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print >> sys.stderr, "Usage: %s <relay host> <relay port>" % sys.argv[0]
        sys.exit(1)

    host = sys.argv[1]
    port = int(sys.argv[2])

    voter = Voter((host, port))
    tornado.ioloop.IOLoop.instance().start()

