from client.client_logic import Player
import Crypto.PublicKey.RSA as RSA
import os
import tornado
from common.helpers import get_account_from_seed

account = get_account_from_seed(3)
print account

p1 = Player("127.0.0.1", 4242, account, "127.0.0.1", 10001)

def main():
	p1.start_encounter("127.0.0.1", 4243, "xxxx")

tornado.ioloop.IOLoop.current().add_callback(main)
tornado.ioloop.IOLoop.current().start()
