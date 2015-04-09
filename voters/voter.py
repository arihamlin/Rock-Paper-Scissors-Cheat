#!/usr/bin/env python

import tornado.log
import tornado.web
import logging
import sys
from comm import VoterNode

tornado.log.enable_pretty_logging()


class Voter(VoterNode):
    def __init__(self, addr, identity):
        VoterNode.__init__(self, addr)
        self.identity = identity

    def on_connect(self):
        self.broadcast_message({
                "event": "register",
                "identity": self.identity
            })

    def on_message(self, msg):
        print msg

    def on_close(self):
        super(self).on_close()
        # clean up


class VoterInterface(tornado.web.RequestHandler):
    def initialize(self, voter):
        self.voter = voter

    def post(self):
        self.finish({})

if __name__ == "__main__":
    if len(sys.argv) != 5:
        print >> sys.stderr, "Usage: %s <relay host> <relay port> <interface port> <identity>" % sys.argv[0]
        sys.exit(1)

    host = sys.argv[1]
    port = int(sys.argv[2])
    infport = int(sys.argv[3])
    identity = sys.argv[4]

    voter = Voter((host, port), identity)
    app = tornado.web.Application([
            (r'/', VoterInterface, dict(voter=voter))
        ])
    tornado.ioloop.IOLoop.instance().start()

