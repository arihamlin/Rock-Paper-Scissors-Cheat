"""
6.857 Project
Purpose: Contains the logic for playing a game client side
Author: ATLH, 4/6/15
"""

from enum import IntEnum
import random
from client_comm import PlayerConnRequestHandler, PlayerServer, Request
from client_crypto import PlayerCrypto

#need to figure out ultimate interface, everything below this is just example code 
def client(ip, port, message):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((ip, port))
    sock.sendall(message)
    response = sock.recv(1024)
    print "Received: {}".format(response)
    sock.close()
        
class Player(object):
    
    def __init__(self, server_ip, server_port, crypto_object):
        
        self.crypto_object = crypto_object 
        #initialize the server
        self.server = ThreadedTCPServer((server_ip, server_port),
                                        crypto_object)

        # Start a thread with the server -- that thread will then start one
        # more thread for each request
        self.server_thread = threading.Thread(target=server.serve_forever)
        # Exit the server thread when the main thread terminates
        self.server_thread.daemon = True
        self.server_thread.start()

    def finish_playing(self):
        """
        Call when done playing before Player goes out of scope
        """
        self.server.shut_down()
        
    def start_encounter(self, player_ip, player_port):
        """
        Arguments:
        player_ip - IP address of the player
        player_port - Port of the other player 
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((player_ip, player_oort))
        sock.sendall("#".join([Request.INIT,
                               random.randint(0,100000),
                               self.crypto_object.sign('Play Game?')]))

    def verify_ledger_state(self):
        """
        Needs to check ledger and make sure all moves are verified
        Will probably need to add some sort of game state to the
        player object where it grabs things when started, 
        keeps track of all the moves, and then can verify 
        at any given time the state of the game. (this implies
        the game transactions need to also come up to 
        this level...)
        """
        pass
        
