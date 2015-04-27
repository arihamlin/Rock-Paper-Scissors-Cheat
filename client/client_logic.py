"""
6.857 Project
Purpose: Contains the logic for playing a game client side
Author: ATLH, 4/6/15
"""
import sys, os.path
sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), os.pardir))

from enum import IntEnum
import random
import socket
import threading
import tornado.httpclient
from client_comm import PlayerConnRequestHandler, Request
import common.base as b
import base64
import tornado.tcpserver
import tornado.tcpclient
import tornado.ioloop
import tornado.gen
import json


class Player(tornado.tcpserver.TCPServer):
    def __init__(self, server_ip, server_port, key, voter_relay_ip, voter_relay_port):
        tornado.tcpserver.TCPServer.__init__(self)
        self.account = b.AccountIdentity(private_key=key)
        #initialize the server
        self.listen(server_port)
        self.voter_relay_ip = voter_relay_ip
        self.voter_relay_port = voter_relay_port

    def finish_playing(self):
        """
        Call when done playing before Player goes out of scope
        """
        tornado.ioloop.IOLoop.current().stop()
    
    @tornado.gen.coroutine
    def start_encounter(self, defender_ip, defender_port, defender_id):
        """
        Arguments:
        player_ip - IP address of the player
        player_port - Port of the other player
        defender_id - the id in the ledger of the defender 
        """
        #talk to voters to determine the begin_by and end_by ledger numbers
        req = b.SignedStructure(b.QueryState(account_id=self.account.account_id))
        req.sign(self.account)

        client = tornado.httpclient.HTTPClient()
        r = client.fetch("http://"+str(self.voter_relay_ip)+":"+str(self.voter_relay_port)+"/?nnodes=1&nresponses=1",
                         method="POST", body=req.serialize())
        results = json.loads(r.body)["responses"]
        if len(results) > 1: 
            print "Not able to get current game state"
            
        deserialized = b.SignedStructure.deserialize(results[0])
        
        if deserialized.payload.name != "AccountState":
            print "Returned value from voter is not an Account State object"
        
        current_ledger = deserialized.payload.current_ledger
        
        begin_by = current_ledger 
        end_by = current_ledger + 600 # Approximately 10 minutes per game
        
        #create initiate encounter object 
        initiate_encounter = b.SignedStructure(b.InitiateEncounter(challenger=self.account.account_id,
                                                 defender=defender_id,
                                                 begin_by=begin_by,
                                                 end_by=end_by),
                                               account=self.account)
        initiate_encounter.sign(self.account)
        
        client = tornado.tcpclient.TCPClient()
        stream = yield client.connect(defender_ip, defender_port)
        stream.write(base64.b64encode("#".join([str(Request.INIT.value),
                                                initiate_encounter.serialize()])) + "\n")
        self.handler = PlayerConnRequestHandler(self.account, 
                                                stream,
                                                self.voter_relay_ip,
                                                self.voter_relay_port)
        yield self.handler.start()

    @tornado.gen.coroutine
    def handle_stream(self, stream, addr):
        self.handler = PlayerConnRequestHandler(self.account, stream,
                                                self.voter_relay_ip,
                                                self.voter_relay_port)
        yield self.handler.start()

        

if __name__ == "__main__":
    tornado.ioloop.IOLoop.current().start()
