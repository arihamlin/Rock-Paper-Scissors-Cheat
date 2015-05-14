from base import AccountIdentity, KEY_SIZE
import os
import random
import Crypto.PublicKey.RSA as RSA


"""
Use random.seed() to deterministically generate public/private
key-pairs (accounts). 
"""

def get_account_from_seed(seed):
	restore = random.getstate()
	random.seed(seed)
	def get_random_bytes(size):
		return "".join([chr(random.getrandbits(4)) for i in xrange(size)])
	key = RSA.generate(KEY_SIZE, get_random_bytes)
	random.setstate(restore)
	return AccountIdentity(private_key=key)
