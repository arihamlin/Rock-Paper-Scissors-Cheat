#!/usr/bin/env python

import tornado.log
import logging
import sys
import consensor
from comm import VoterNode

tornado.log.enable_pretty_logging()


class Voter(VoterNode):
    def __init__(self, relay_host, account_id):
        VoterNode.__init__(self, relay_host)
        self.account_id = account_id
        private_key = "asdf" #TODO: fix this
        self.consensor = Consensor(account_id, private_key)
        self.consensor.start()

    def on_connect(self):
        self.broadcast_message({
                "event": "register",
                "account_id": self.account_id
            })

    def on_message(self, sender_id, msg):
        pass

    def on_voter_message(self, msg):
        self.consensor.

    def on_close(self):
        VoterNode.on_close(self)
        # clean up


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print >> sys.stderr, "Usage: %s <relay host> <relay port> <account_id>" % sys.argv[0]
        sys.exit(1)

    host = sys.argv[1]
    port = int(sys.argv[2])
    infport = int(sys.argv[3])
    account_id = sys.argv[4]

    voter = Voter((host, port), account_id)
    tornado.ioloop.IOLoop.instance().start()

