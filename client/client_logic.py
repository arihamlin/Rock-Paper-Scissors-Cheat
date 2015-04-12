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
from client_comm import PlayerConnRequestHandler, Request
import common.base as b
import base64
import tornado.tcpserver
import tornado.tcpclient
import tornado.ioloop
import tornado.gen


class Player(tornado.tcpserver.TCPServer):
    def __init__(self, server_ip, server_port, key):
        tornado.tcpserver.TCPServer.__init__(self)
        self.account = b.AccountIdentity(private_key=key)
        #initialize the server
        self.listen(server_port)

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
        #check to see if defender is in a game
        #TODO
        
        #talk to voters to determine the begin_by and end_by ledger numbers
        #TODO: talk to server to get current state
        begin_by = 0
        end_by = 0
        
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
        self.handler = PlayerConnRequestHandler(self.account, stream)
        self.handler.start()


    def handle_stream(self, stream, addr):
        self.handler = PlayerConnRequestHandler(self.account, stream)
        self.handler.start()

    def get_ledger_state(self):
        """
        get current ledger state, take state which most voters agree on. 
        """
        pass
        

if __name__ == "__main__":
    tornado.ioloop.IOLoop.current().start()
