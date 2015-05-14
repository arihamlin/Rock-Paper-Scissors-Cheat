from client.client_logic import Player
import Crypto.PublicKey.RSA as RSA
import os
import tornado
from common.helpers import get_account_from_seed

"""
Example challenger listens on port 4242 and uses account seed 3.
It connects to example defender which listens on port 4243. 
"""

account = get_account_from_seed(3)
print account

p1 = Player("127.0.0.1", 4242, account, "127.0.0.1", 10001)

def main():
	p1.start_encounter("127.0.0.1", 4243, "YjNhMzI2MGFmMWEyM2M4MGE5YTIzYzA2NzU0OTc4YjdjOGU4") # ID of my opponent

tornado.ioloop.IOLoop.current().add_callback(main)
tornado.ioloop.IOLoop.current().start()
