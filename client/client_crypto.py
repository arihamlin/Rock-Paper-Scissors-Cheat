"""
6.857 Project
Purpose: Contains the logic for client crypto
Author: ATLH, 4/6/15
"""

class PlayerCrypto(object):
    """
    Contains the logic for signing, commiting, and hashing messages
    """
    def __init__(self):
        pass
    
    def sign(self, message):
        return message
    
    def verify(self, digest, message):
        #this needs to initialized with other player's verification key, 
        #guess need some notion of identity as well
        return message == message
    
    def commit(self, message):
        return message
    
    def reveal_correct(self, commitment, move):
        #this needs to check if other players commitment matches, may
        # need some notion of other player's Identity
        return move == commitment
    
    def hash(self, message):
        return message
