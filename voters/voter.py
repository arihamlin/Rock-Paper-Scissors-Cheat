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
        self.consensor = Consensor(self, self.account)
        self.consensor.start()

    def on_connect(self):
        pass

    def on_message(self, sender_id, msg):
        if "event" in msg and msg["event"] == "client_request":
            self.on_client_message(sender_id, msg)
        else:
            self.on_voter_message(sender_id, msg)

    def send_voter_message(self, msg):
        msg["event"] = "voter_message"
        msg["account_id"] = self.account_id
        self.broadcast_message(msg)


    def on_client_message(self, sender_id, msg):
        """
        Voters receive few types of messages from client:
        1. QueryState
        2. PostInitiateEncounter
        3. CloseEncounter

        QueryState is handled directly by Voter and returns
        the current state given an account ID from ledger.

        PostInitiateEncounter and CloseEncounter are handled
        by Consensor and does not return with immediate response.
        """

        req = msg["request"].decode("base64")
        signed = SignedStructure.deserialize(req)
        #print "Client request: ", signed
        if signed.payload.name == "QueryState":
            query_account_id = signed.payload.account_id
            info = self.consensor.last_closed_ledger.get_account_info(query_account_id)

            state = AccountState(**info)
            signed = SignedStructure(state)
            signed.sign(self.account)
            self.send_message(sender_id, {
                "result": signed.serialize()
            })
        else:
            #logging.info("GOT REQUEST:"+signed.payload.name)
            self.consensor.consider_transaction(signed)

    def on_voter_message(self, sender_id, msg):
        #logging.info("GOT MESSAGE FROM OTHER VOTER:"+str(sender_id)+":"+str(msg))
        self.consensor.process_voter_message(sender_id, msg)

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

