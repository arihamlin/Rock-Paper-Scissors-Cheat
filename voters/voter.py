#!/usr/bin/env python
import sys, os.path
sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), os.pardir))

import tornado.log
import logging
import sys
from consensor import Consensor
from common.base import AccountState, SignedStructure, QueryState
from comm import VoterNode
from common.helpers import get_account_from_seed

tornado.log.enable_pretty_logging()


class Voter(VoterNode):
    def __init__(self, relay_host, seed):
        VoterNode.__init__(self, relay_host)
        self.account = get_account_from_seed(seed)
        self.account_id = self.account.account_id
        self.consensor = Consensor(self.account)
        self.consensor.start()

    def on_connect(self):
        self.broadcast_message({
                "event": "register",
                "account_id": self.account_id
            })

    def on_message(self, sender_id, msg):
        print msg
        if "event" in msg and msg["event"] == "client_request":
            self.on_client_message(sender_id, msg)
        else:
            self.on_voter_message(sender_id, msg)

    def on_client_message(self, sender_id, msg):
        req = msg["request"].decode("base64")
        signed = SignedStructure.deserialize(req)
        print "Client request: ", signed
        if signed.payload.name == "QueryState":
            query_account_id = signed.payload.account_id
            state = AccountState(account_id=query_account_id,
                encounter_begin_at=0,
                encounter_end_by=0,
                in_encounter_with="",
                partial_chain_length=0,
                stake=0,
                balance=0)
            signed = SignedStructure(state)
            signed.sign(self.account)  #TODO: use voter's account
            self.send_message(sender_id, {
                "result": signed.serialize()
            })
        else:
            # handle unknown client request
            pass

    def on_voter_message(self, sender_id, msg):
        self.consensor.process_transaction(msg)

    def on_close(self):
        VoterNode.on_close(self)
        # clean up


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print >> sys.stderr, "Usage: %s <relay host> <relay port> <account_seed>" % sys.argv[0]
        sys.exit(1)

    host = sys.argv[1]
    port = int(sys.argv[2])
    seed = int(sys.argv[3])

    voter = Voter((host, port), seed)
    tornado.ioloop.IOLoop.instance().start()

