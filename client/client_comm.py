"""
6.857 Project
Purpose: Contains the logic for client communication with
other clients and the server 
Author: ATLH, 4/6/15
"""
from __future__ import print_function
import socket
import SocketServer
import random
import time 
import sys
import threading
import tornado.httpclient
from enum import IntEnum
import common.base as b
import base64 
import tornado.gen
import json
import logging

WINS = {('R','S'): 0,
        ('R','P'): 1,
        ('R','R'): -1,
        ('P','R'): 0,
        ('P','S'): 1,
        ('P','P'): -1,
        ('S','R'): 0,
        ('S','P'): 1,
        ('S','S'): -1}

class CommunicationException(Exception):
    pass

class Request(IntEnum):
    """
    Different type of requests the clients can handle:
    INIT - Game request from the challenger, defender recieves
           if accepts, sends commitment and initializes encounter
           with the voters 
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
    
    

class PlayerConnRequestHandler(object):
    def __init__(self, account, stream, voter_relay_ip, voter_relay_port):
        print("Connected: ", account)
        self.account = account
        self.stream = stream
        self.moves = []
        self.rounds = 0
        self.voter_relay_ip = voter_relay_ip
        self.voter_relay_port = voter_relay_port

    def send_data(self, s):
        self.stream.write(base64.b64encode(s) + "\n")
        print("Sent data: " + s)

    @tornado.gen.coroutine
    def start(self):
        print("Start")
        self.timeout_handle = tornado.ioloop.IOLoop.current(
            ).call_later(600, self.on_timeout)
        while True:
            try:
                line = yield self.stream.read_until("\n")
                self.on_line(line)
            except Exception, ex:
                print("CONNECTION CLOSED!!")
                logging.info("CONNECTION CLOSED!")
                break

        # tornado.ioloop.IOLoop.current().remove_timeout(self.timeout_handle)

    def on_line(self, line):
        data = base64.b64decode(line)
        print("Received data: " + data)
        req = int(data.split('#')[0])        
        payload = data.split('#')[1]
        
        transaction = b.SignedStructure.deserialize(payload)
        
        #verify signature 
        if not transaction.verifySignature(transaction.account.account_id):
            print("Error: Transaction signature does not verify",file=sys.stderr)
            return
        
        if req == Request.INIT:    
            self.initialize_encounter(transaction)
        elif req == Request.D_COMMIT:
            self.rounds +=1
            self.defender_commit(transaction)
        elif req == Request.C_COMMIT:
            self.rounds += 1
            self.challenger_commit(transaction)
        elif req == Request.D_REVEAL:
            self.defender_reveal(transaction)
        elif req == Request.C_REVEAL:
            self.challenger_reveal(transaction)
        elif req == Request.RESOLVE:
            self.resolve_game(transaction)

    def on_timeout(self):
        #TODO - deal with ragequit case (timeout)
        pass

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
        
        #wait for user_input to get set - 
        timeout = time.time() + 60
        while user_input[0] == None and time.time() < timeout:
            time.sleep(1)
            continue   
        
        return user_input[0]
    
    def _commit_turn(self, prev):
        #Get player input for turn
        turn = self._get_player_input("What would you like to play - Rock(R), Paper(P), Scissors(S) ")
    
        #sanitize user input
        if turn not in ['R','P','S']:
            turn = random.choice(['R','P','S'])
            print("Option not understood or not chosen, choosing ", turn,file=sys.stderr)
        
        #Commit to turn and send that to challenger
        self.my_turn = b.Commitment(input=turn)
        commit_transaction = b.SignedStructure(b.CommitTransaction(prev=prev, 
                                                                  commitment=self.my_turn.serialize()), 
                                              account=self.account)
        commit_transaction.sign(self.account)
        
        return commit_transaction
    
    def _reveal_turn(self, prev):
        reveal_transaction = b.SignedStructure(b.RevealTransaction(prev=prev,
                                                                   value=self.my_turn.input,
                                                                   secret=base64.b64encode(self.my_turn.secret)),
                                               account=self.account)
        reveal_transaction.sign(self.account)
        
        return reveal_transaction
    
    def _verify_commitment(self, reveal_transaction):
        value = reveal_transaction.value
        secret = base64.b64decode(reveal_transaction.secret)
        commitment = b.Commitment.deserialize(self.moves[-3].payload.commitment)
        return commitment.verifyCommitment(secret, value)
    
    def _handle_win(self, my_reveal, other_player_reveal):
        my_val = my_reveal.payload.value
        their_val = other_player_reveal.payload.value
        outcome = WINS[(my_val, their_val)]
        if outcome == 1:
            print("The other player played",their_val,
                  "to your", my_val, "and you lost.")
        elif outcome == 0:
            print("The other player played",their_val,
                  "to your", my_val, "and you won.")
        else:
            print("The other player played",their_val,
                  "to your", my_val, "and you tied.")
            
    def _post_request_to_voters(self, req):
        #talk to voters to determine the begin_by and end_by ledger numbers
        print("POSTING TO VOTERS!!!"+str(req))
        #import pdb
        #pdb.set_trace()
        client = tornado.httpclient.HTTPClient()
        r = client.fetch("http://"+str(self.voter_relay_ip)+":"+str(self.voter_relay_port)+"/?nnodes=1&nresponses=0",
                         method="POST", body=req.serialize())
    
    @tornado.gen.coroutine
    def _get_account_state(self):
        #talk to voters to determine the account state
        req = b.SignedStructure(b.QueryState(account_id=self.account.account_id))
        req.sign(self.account)

        client = tornado.httpclient.AsyncHTTPClient()
        r = yield client.fetch("http://"+str(self.voter_relay_ip)+":"+str(self.voter_relay_port)+"/?nnodes=1&nresponses=1",
                         method="POST", body=req.serialize())
        
        results = json.loads(r.body)["responses"]
        if len(results) > 1: 
            print("Not able to get current game state")

        deserialized = b.SignedStructure.deserialize(results[0])
        
        if deserialized.payload.name != "AccountState":
            print("Returned value from voter is not an Account State object")
        
        raise tornado.gen.Return(deserialized)
        
    @tornado.gen.coroutine
    def initialize_encounter(self, transaction): 
        assert transaction.payload.name == "InitiateEncounter"
        
        
        play_game = self._get_player_input("Play a game (Y/N): ")
        
        if play_game is None or play_game.upper() != 'Y':
            return 
        
        #Sign the encounter and post to the server
        init = transaction.payload
        init_transaction = b.SignedStructure(b.PostInitiateEncounter(challenger=init.challenger,
                                                   defender=init.defender,
                                                   begin_by=init.begin_by,
                                                   end_by=init.end_by,
                                                   challenger_sign=transaction.signature))
        init_transaction.sign(self.account)
        self._post_request_to_voters(init_transaction)
        
        #Wait until can get encounter_start at 
        #TODO: actually check this value
        account_state = yield self._get_account_state()
        print(account_state)
        encounter_start_at = account_state.payload['encounter_begin_at']
        
        #get player turn and get the commitment 
        commit_transaction = self._commit_turn(encounter_start_at)
        self.moves.append(commit_transaction)
        self.send_data("#".join([str(Request.D_COMMIT.value),
                                                  commit_transaction.serialize()]))
    
    @tornado.gen.coroutine
    def defender_commit(self, transaction):
        assert transaction.payload.name =="CommitTransaction"
        self.moves.append(transaction)
        
        #check to see if defender has posted to voters yet    
        account_state = yield self._get_account_state()
        if account_state.payload['in_encounter_with'] != transaction.account.account_id:
            print("Encounter hasn't started yet")
            #TODO: loop here until it is posted
        
        #get player turn and get the commitment
        commit_transaction = self._commit_turn(transaction.signature)
        self.moves.append(transaction)
        self.send_data("#".join([str(Request.C_COMMIT.value),
                                                  commit_transaction.serialize()]))
        
    def challenger_commit(self, transaction):
        assert transaction.payload.name == "CommitTransaction"
        self.moves.append(transaction)
        #construct reveal transaction object for defender
        reveal_transaction = self._reveal_turn(transaction.signature)
        self.moves.append(reveal_transaction)
        self.send_data("#".join([str(Request.D_REVEAL.value),
                                                  reveal_transaction.serialize()]))
        
    def defender_reveal(self, transaction):
        assert transaction.payload.name == 'RevealTransaction'
        self.moves.append(transaction)
        #check that the commitment is valid
        if not self._verify_commitment(transaction.payload):
            print("Error: Commitment is not valid",file=sys.stderr)
            return 
        
        #construct reveal transaction object for challenger
        reveal_transaction = self._reveal_turn(transaction.signature)
        self.moves.append(reveal_transaction)
        self._handle_win(self.moves[-1], self.moves[-2])
        self.send_data("#".join([str(Request.C_REVEAL.value),
                                                  reveal_transaction.serialize()]))
    
    def challenger_reveal(self, transaction):
        assert transaction.payload.name == 'RevealTransaction'
        self.moves.append(transaction)
        #check that the commitment is valid
        if not self._verify_commitment(transaction.payload):
            print("Error: Commitment is not valid",file=sys.stderr)
            return 
        
        self._handle_win(self.moves[-2], self.moves[-1])
        #two paths, either 3 rounds have happened or not
        #or not
        if self.rounds < 3:
            commit_transaction = self._commit_turn(transaction.signature)
            self.moves.append(commit_transaction)
            self.send_data("#".join([str(Request.D_COMMIT.value),
                                                  commit_transaction.serialize()]))
        #else send resolution
        else:
            resolve_transaction = b.SignedStructure(b.Resolution(prev=transaction.signature),
                                                account=self.account)
            resolve_transaction.sign(self.account)
            self.moves.append(resolve_transaction)
            self.send_data('#'.join([str(Request.RESOLVE.value),
                                                  resolve_transaction.serialize()]))
            tornado.ioloop.IOLoop.current().stop()
        
            #post to the server to close the encounter 
            serialized_moves = "#".join([m.serialize() for m in self.moves])
            close_transaction = b.SignedStructure(b.CloseEncounter(
                                                        challenger=transaction.account.account_id,
                                                        defender=self.account.account_id,
                                                        moves=serialized_moves))
            close_transaction.sign(self.account)
            self._post_request_to_voters(close_transaction)
        
    @tornado.gen.coroutine
    def resolve_game(self, transaction):
        assert transaction.payload.name == "Resolution"
        self.moves.append(transaction)
        
        #checks to see if the defender posted correctly to close encounter
        account_state = yield self._get_account_state()
        if account_state.payload['in_encounter_with'] is not None: #account_state['in_encounter_with'] != '': #TODO may also want to check chain length 
            #post to the server to close the encounter 
            serialized_moves = "#".join([m.serialize() for m in self.moves])
            close_transaction = b.SignedStructure(b.CloseEncounter(
                                                        challenger=transaction.account.account_id,
                                                        defender=self.account.account_id,
                                                        moves=serialized_moves))
            close_transaction.sign(self.account)
            self._post_request_to_voters(close_transaction)


        tornado.ioloop.IOLoop.current().stop()
        
         

    