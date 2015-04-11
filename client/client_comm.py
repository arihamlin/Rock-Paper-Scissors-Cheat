"""
6.857 Project
Purpose: Contains the logic for client communication with
other clients and the server 
Author: ATLH, 4/6/15
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
    D_COMMIT - Defender player has acknowledge request and returned
               their commitment, challenger have also have to 
               check with the server state that defender posted
               game before continuing and responding with their 
               commitment 
    C_COMMIT - Defender recieves challengers commitment, they
               respond with revealing their turn
    D_REVEAL - Challenger recieves the defenders reveal, and verify
               the commitment they respond with revealing their own turn. 
    C_REVEAL - Defender recieves challengers reveal, and verify the 
               commitment. There are two possiblities at this point:
               1) if have not had three enounters yet they send
               another commitment to the challenger. 
               2) if they have had three they then send a resolve
                to the challanger and post a record of the moves
                to the voters
    RESOLVE - Sent by the defender after three encounters to
              the challenger. Challenger then checks to see
              if the defender has posted the correct things
              to the voters. 
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
        self.moves = []
        self.socket_file = self.request.makefile()
        num_transactions = 0
        
        while num_transactions < 13 #TODO - or timeout:
            num_transactions += 1 
            data = self.socket_file.readline().strip()
            req = data.split('#')[0]        
            payload = data.split('#')[1:]
            
            transaction = SignedStructure.deserialize(payload)
            #TODO Verify signature on transaction
            
            if req == Request.INIT:            
                self.initialize_encounter(transaction)
            elif req == Request.D_COMMIT:
                self.defender_commit(transaction)
            elif req == Request.C_COMMIT:
                self.challenger_commit(transaction)
            elif req == Request.D_REVEAL:
                self.defender_reveal(transaction)
            elif req == Request.C_REVEAL:
                self.challenger_reveal(transaction)
            elif req == Request.RESOLVE:
                self.resolve_game(transaction)
            else:
                continue
            
    def _get_player_input(self, prompt): 
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
        
        #wait for user_input to get set - TODO: may want to time this out...
        while user_input[0] == None:
            continue   
        
        return user_input[0]
    
    def _commit_turn(self, prev):
        #Get player input for turn
        self.turn = self._get_player_input("What would you like to play - Rock(R), Paper(P), Scissors(S) ")
    
        #sanitize user input
        if self.turn not in ['R','P','S']:
            #TODO: In the future lets randomize this 
            print "Option not understood, choosing Rock."
            self.turn = 'R'
        
        #Commit to turn and send that to challenger
        commitment = b.CommitStructure(self.turn)
        commitment.commit()
        commt_transaction = b.SignedStructure(b.CommitTransaction(prev=prev, 
                                                                  commitment=commitment.serialize()))
        commit_transaction.sign(self._PlayerServer.key)
        self.moves.append(commit_transaction)
        return commit_transaction
    
    def _reveal_turn(self, prev):
        reveal_transaction = b.SignedStructure(b.RevealTransaction(prev=prev,
                                                                   value=self.turn))
        reveal_transaction.sign(self._PlayerServer.key)
        self.moves.append(reveal_transaction)
        return reveal_transaction
    
    def initialize_encouter(self, transaction): 
        assert transaction.payload.name == "InitiateEncounter"
        
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
        
        #get player turn and get the commitment 
        commit_transaction = self._commit_turn(encounter_start_at)
        self.request.send("#".join([Request.D_COMMIT,commit_transaction.serialize()]))
        
    def defender_commit(self, transaction):
        assert transaction.payload.name =="CommitTransaction"
        
        #check to see if defender has posted to voters yet    
        #TODO - check to see if defender has posted to voters
        has_init = True
        
        #get player turn and get the commitment
        commit_transaction = self._commit_turn(transaction.signature)
        self.request.send("#".join([Request.C_COMMIT,commit_transaction.serialize()]))
        
    def challenger_commit(self, transaction):
        assert transaction.payload.name == "CommitTransaction"
        
        #construct reveal transaction object for defender
        reveal_transaction = self._reveal_turn(transaction.signature)
        self.request.send("#".join([Request.D_REVEAL,reveal_transaction.serialize()]))
        
    def defender_reveal(self, transaction):
        assert transaction.payload.name == 'RevealTransaction'
        
        #check that the commitment is valid
        #TODO: check commitment value
        
        #construct reveal transaction object for challenger
        reveal_transaction = self._reveal_turn(transaction.signature)
        self.request.send("#".join([Request.D_REVEAL,reveal_transaction.serialize()]))
    
    def challenger_reveal(self, transaction):
        assert transaction.payload.name == 'RevealTransaction'
        
        #check that the commitment is valie
        #TODO check commitment value
        
        #send resolution
        resolve_transaction = b.SignedStructure(b.ResolveTransaction(prev=transaction.signature))
        resolve_transaction.sign(self._PlayerServer.key)
        self.moves.append(resolve_transaction)
        self.request.send('#'.join([Request.RESOLVE,resolve_transaction.serialize()]))
        
        #post to the server to close the encounter 
        #TODO post to server to close encounter
        
    def resolve_game(self, transaction):
        assert transaction.payload.name == "ResolveTransaction"
        
        #checks to see if the defender posted correctly to close encounter
        #TODO - query game state and see if no longer in encounter 
        
        
        
        
        
    
        
class PlayerServer(SocketServer.TCPServer):
    def __init__(self, server_address, key, handler_class=PlayerConnRequestHandler):
        SocketServer.TCPServer.__init__(self, server_address, handler_class)
        self.key = key

    