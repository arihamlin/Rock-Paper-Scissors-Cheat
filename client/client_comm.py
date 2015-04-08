"""
6.857 Project
Purpose: Contains the logic for client communication with
other clients and the server 
Author: ATLH, 4/6/15
"""
"""
NOTES OF TODO:
1) need to figure out how communication with the server is going to look like -
this seems to make sense that it is HTTP post and get this only really comes into
the posting of end, and verifying - this needs to be done and also 
handling who wins 
2) also need interface for initiating game - at this point it may make sense
just to send an INIT request cold outside of the handler. 
3) need to expand have checking to make sure encounter id matches current encounter
"""

import socket
import threading
import SocketServer
from enum import import IntEnum

class CommunicationException(Exception):
    pass

class Request(IntEnum):
    """
    Different type of requests the clients can handle, all
    games include a encounter id
    INIT - Initialize a game, the payload is the signed 
           game statement from the other player
    ACK_INIT - Other player has acknowledge request, the
            payload is a yes/no answer and if yes, the signed
            game reciept
    COMMIT - Other player's turn commitment
    REVEAL - Reveal of the other player's turn 
    RESOLVE - Resolve game and post results to the server, 
    DONE - Sent when encounter/game is done. 
    """
    INIT = 1 
    ACK_INIT = 2 
    COMMIT = 3 
    REVEAL = 4
    RESOLVE = 5
    DONE = 6
    

    

class PlayerConnRequestHandler(SocketServer.BaseRequestHandler):

    def handle(self):
        #initialize encounter variables 
        self.socket_file = self.request.makefile()
        self.data = self.socket_file.readline().strip()
        self.game_transaction = {'encounter_id' : None, 
                                 'signed_init' : None,
                                 'my_turn' : None,
                                 'my_turn_commitment' : None, 
                                 'their_turn': None,
                                 'their_turn_commitment' : None,
                                 'sigma1' : None,
                                 'sigma2' : None,
                                 'sigma3' : None, 
                                 'sigma4' : None}
        
        req, payload = self.data.split('#')
        ##TODO: need to deal with the case where other player leaves this loop hanging
        while req != Request.DONE:
            #case where another player wants to start encounter
            if req == Request.INIT:            
                self.initialize_encounter(payload)
            #responding to person and their encounter
            elif req == Request.ACK_INIT:
                self.start_encounter(payload)
            #recieved other player's commit.
            elif req == Request.COMMIT:
                self.reveal_commitment(payload)
            elif req == Request.REVEAL:
                self.reveal_second_commit(payload)
            elif req == Request.RESOLVE:
                self.resolve_game(payload)
                break
            else:
                continue
            self.data = self.socket_file.readline().strip()
            req, payload = self.data.split('#')
            
    def initialize_encouter(self, payload):
        ##1. 
        # Declare a mutable object so that it can be pass via reference
        user_input = [None]

        # spawn a new thread to wait for input 
        def get_user_input(user_input_ref):
            user_input_ref[0] = raw_input("Play a game (Y/N): ")

        input_thread = threading.Thread(target=get_user_input, args=(user_input,))
        input_thread.daemon = True
        input_thread.start()
        
        #wait for user_input to get set - may want to time this out...
        while user_input[0] == None:
            continue
        
        #sanitize user input 
        play_game = user_input[0]
        if not (play_game == "Y" or play_game = "N"):
            print "Option not understood, declining game."
            play_game = "N"
        
        try:
            encounter_id, signed = payload
        except:
            raise CommunicationException("Payload not properly formatted")
        
        #set current encounter and sign the game chit
        self.game_transaction['signed_init'] = self._PlayerServer.crypto.sign(signed)
        self.game_transaction['encounter_id'] = encounter_id
        request = "#".join([Request.ACK_INIT,
                            self.game_transaction['encounter_id'],
                            play_game,
                            self.game_transaction['signed_init'])
        self.game_transaction['sigma1'] = self._PlayerServer.crypto.sign(request)
        
        #send response
        self.request.send("#".join([request,self.game_transaction['sigma1']]))
    
    def start_encounter(self, payload):
        ##2
        #figure out if game is going forward
        try:
            encounter_id, play_game, signed_game, sigma1 = payload
        except:
            raise CommunicationException("Payload not properly formatted")
        
        #verify_signature on transaction
        message = "#".join([Request.ACK_INIT,
                            encounter_id,
                            play_game,
                            signed_game))
        if not self._PlayerServer.crypto.verify(message, sigma1) and\
           not self._PlayerServer.crypto,verify('Play Game?',signed_game):
            print "Did not come from valid player, terminating"
            return 
        
        #doesn't want to play a game...:( 
        if play_game != 'Y':
            return 
        
        # Declare a mutable object so that it can be pass via reference
        user_input = [None]

        # spawn a new thread to wait for input 
        def get_user_input(user_input_ref):
            user_input_ref[0] = raw_input("What would you like to play - Rock(R), Paper(P), Scissors(S) ")

        input_thread = threading.Thread(target=get_user_input, args=(user_input,))
        input_thread.daemon = True
        input_thread.start()
        
        #wait for user_input to get set = may want to time this out...
        while user_input[0] == None:
            continue
        
        #sanitize user input
        if user_input[0] not in ['R','P','S']:
            #TODO: In the future lets randomize this 
            print "Option not understood, choosing Rock."
            user_input[0] = 'R'
        
        #calculate commitment
        self.game_transaction['my_turn'] = user_input[0]
        self.game_transaction['my_turn_commitment'] = 
                    self._PlayerServer.crypto.commit(self.current_move)   
        self.game_transaction['sigma1'] = sigma1 
        self.game_transaction['signed_init'] = signed_game
        
        #calculate sigma2
        message = "#".join([Request.COMMIT,
                            self.game_transaction['encounter_id'],
                            self.game_transaction['my_turn_commitment'],
                            self.game_transaction['sigma1']))
        self.game_transaction['sigma2'] = self._PlayerServer.crypto.sign(message)
        
        #send the commitment
        self.request.send("#".join([message,self.game_transcript['sigma2']]))
        
    def reveal_commitment(self, payload):
        ##3
        #extract their commitment
        try:
            encounter_id, their_commit, sigma1, sigma2 = payload
        except:
            raise CommunicationException("Payload not properly formatted")
        
        #verify_signature on transaction
        message = "#".join([Request.COMMIT,
                            encounter_id,
                            their_commit,
                            sigma1))
        if not self._PlayerServer.crypto.verify(message, sigma2):
            print "Did not come from valid player, terminating"
            return
        
        #sign reveal and send 
        request = '#'.join([Request.REVEAL,
                            self.game_transaction['encounter_id'],
                            self.game_transaction['my_turn'],
                            self.game_transaction['sigma2']])
        self.game_transaction['sigma3'] = self._PlayerServer.crypto.sign(request)
        self.request.send('#'.join([request,self.game_transaction['sigma3']]))
        
    def reveal_second_commit(self, payload):
        ##4
        #extract their turn 
        try:
            encounter_id, their_turn, sigma2, sigma3 = payload
        except:
            raise CommunicationException("Payload not properly formatted")
        
        message = "#".join([Request.COMMIT,
                            encounter_id,
                            their_turn,
                            sigma2))
        if not self._PlayerServer.crypto.verify(message, sigma3):
            print "Did not come from valid player, terminating"
            return
        
        self.game_transaction['their_turn'] = their_turn
        #verify their commitment
        if self._PlayerServer.crypto.reveal_correct(
                            self.game_transaction['their_turn_commitment'],
                            self.game_transaction['their_turn']):
            print "Other player's commitment did not reveal to their claimed turn, terminating"
            return
        
        #send own turn 
        request = '#'.join([Request.RESOLVE,
                            self.game_transaction['encounter_id'],
                            self.game_transaction['my_turn'],
                            self.game_transaction['sigma3']])
        self.game_transaction['sigma4'] = self._PlayerServer.crypto.sign(request)
        self.request.send('#'.join([request,self.game_transaction['sigma4']]))
        
        #figure out who won and post game transaction to server, this 
        #functionality is the same so create another function for resolve to also call
        
    def resolve_game(self, payload):
        ##5
        #extract their turn 
        try:
            encounter_id, their_turn, sigma3, sigma4 = payload
        except:
            raise CommunicationException("Payload not properly formatted")
        
        
        if not self._PlayerServer.crypto.verify(message, sigma3):
            print "Did not come from valid player, terminating"
            return
        
        #set final variables in game_transaction
        self.game_transaction['their_turn'] = their_turn
        self.game_transaction['sigma4'] = sigma4

        #verify their commitment
        if self._PlayerServer.crypto.reveal_correct(
                            self.game_transaction['their_turn_commitment'],
                            self.game_transaction['their_turn']):
            print "Other player's commitment did not reveal to their claimed turn, terminating"
            return
        
        #figure out who won and post game transaction to server, this 
        #functionality is the same so create another function for resolve to also call
        self.request.send('#'.join([Request.DONE, 
                                    self.game_transaction['encounter_id']])
        
class PlayerServer(SocketServer.ThreadingMixIn, SocketServer.TCPServer):
    def __init__(self, server_address, crypto, handler_class=PlayerConnRequestHandler):
        SocketServer.TCPServer.__init__(self, sever_address, handler_class)
        self.crypto = crypto

    