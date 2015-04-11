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
handling who wins (this is going to be handled by manu)
2) need to expand have checking to make sure encounter id matches current encounter
3) need to only allow one game played at a time (don't want it threaded) 
4) 
"""

import socket
import SocketServer
from enum import IntEnum
import common.base as b

class CommunicationException(Exception):
    pass

class Request(IntEnum):
    """
    Different type of requests the clients can handle:
    INIT - Game request from the challenger, defender recieves
           if accepts, sends commitment and initializes encounter
           with the server - they also have to define the
           encounter begins at
    D_COMMIT - Defender player has acknowledge request, the
            returns their commitment, they have also have to 
            check with the server state that defender posted
            game before continuing.  
    C_COMMIT - Challengers turn commitment
    D_REVEAL - Reveal of the Defender's turn 
    C_REVEAL - Reveal of the Challenger's turn
    RESOLVE - Sent by the defender after three encounters 
             indicates that they have posted results to 
             server and challenger should do the same 
    """
    INIT = 1 
    D_COMMIT = 2 
    C_COMMIT = 3 
    D_REVEAL = 4
    C_REVEAL = 5
    RESOLVE = 6
    

    

class PlayerConnRequestHandler(SocketServer.BaseRequestHandler):

    def handle(self):
        #initialize encounter variables 
        self 
        self.socket_file = self.request.makefile()
        num_transactions = 0
        
        while num_transactions < 7 #or timeout:
            num_transactions += 1 
            data = self.socket_file.readline().strip()
            req = data.split('#')[0]        
            payload = data.split('#')[1:]
            
            transaction = SignedStructure.deserialize(payload)
            #TODO Verify signature on transaction
            
            #case where another player wants to start encounter
            if req == Request.INIT:            
                self.initialize_encounter(transaction)
            #responding to defenders commitment
            elif req == Request.D_COMMIT:
                self.defender_commit(transaction)
            #responding to challenger's commitment
            elif req == Request.C_COMMIT:
                self.challenger_commitment(transaction)
            #responding to defenders reveal
            elif req == Request.D_REVEAL:
                self.defender_reveal(transaction)
            #responding to challeners reveal
            elif req == Request.C_REVEAL:
                self.challenger_reveal(transaction)
            #resolving the game 
            elif req == Request.RESOLVE:
                self.resolve_game(transaction)
            else:
                continue
            
    def get_player_input(self, prompt): 
        """
        Arguments:
        prompt - the prompt for the user 
        
        Returns: user input
        """
        user_input = [None]

        # spawn a new thread to wait for input 
        def get_user_input(user_input_ref):
            user_input_ref[0] = raw_input(prompt)

        input_thread = threading.Thread(target=get_user_input, args=(user_input,))
        input_thread.daemon = True
        input_thread.start()
        
        #wait for user_input to get set - may want to time this out...
        while user_input[0] == None:
            continue   
        
        return user_input[0]
    
    def initialize_encouter(self, transaction): 
 
        assert type(transaction.payload) == b.InitiateEncounter
        
        play_game = self.get_player_input("Play a game (Y/N): ")
        
        if play_game != 'Y':
            return 
        
        #Sign the encounter and post to the server
        transaction.payload['challenger_sign'] = transaction.signature
        init_transaction = b.PostIntiateEncounter(*transaction.payload.__dict__)
        #TODO: post to the server 
        
        #Wait until can get encounter_start at
        #TODO: query server and get encounter start at
        encounter_start_at = 0
        
        #Get player input for turn
        turn = self.get_player_input("What would you like to play - Rock(R), Paper(P), Scissors(S) ")
    
        #sanitize user input
        if turn not in ['R','P','S']:
            #TODO: In the future lets randomize this 
            print "Option not understood, choosing Rock."
            user_input[0] = 'R'
        
        #Commit to turn and send that to challenger
        
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
                            signed_game])
        if not self._PlayerServer.crypto.verify(message, sigma1) and\
           not self._PlayerServer.crypto.verify('Play Game?',signed_game):
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
        self.game_transaction['my_turn_commitment'] = \
                    self._PlayerServer.crypto.commit(self.current_move)   
        self.game_transaction['sigma1'] = sigma1 
        self.game_transaction['signed_init'] = signed_game
        
        #calculate sigma2
        message = "#".join([Request.COMMIT,
                            self.game_transaction['encounter_id'],
                            self.game_transaction['my_turn_commitment'],
                            self.game_transaction['sigma1']])
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
                            sigma1])
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
                            sigma2])
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
                                    self.game_transaction['encounter_id']]))
        
class PlayerServer(SocketServer.TCPServer):
    def __init__(self, server_address, crypto, handler_class=PlayerConnRequestHandler):
        SocketServer.TCPServer.__init__(self, server_address, handler_class)
        self.crypto = crypto

    