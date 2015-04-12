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
import SocketServer
from client_comm import PlayerConnRequestHandler, PlayerServer, Request
import common.base as b
import base64
        
class Player(object):
    
    def __init__(self, server_ip, server_port, key):
        
        self.account = b.AccountIdentity(private_key=key)
        #initialize the server
        self.server = PlayerServer((server_ip, server_port),
                                    account=self.account)

        # Start a thread with the server 
        self.server_thread = threading.Thread(target=self.server.serve_forever)
        # Exit the server thread when the main thread terminates
        self.server_thread.daemon = True
        self.server_thread.start()

    def finish_playing(self):
        """
        Call when done playing before Player goes out of scope
        """
        self.server.shutdown()
        
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
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((defender_ip, defender_port))
        sock.sendall(base64.b64encode("#".join([str(Request.INIT.value),
                                                initiate_encounter.serialize()])))

    def get_ledger_state(self):
        """
        get current ledger state, take state which most voters agree on. 
        """
        pass
        
