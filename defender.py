from client.client_logic import Player
import Crypto.PublicKey.RSA as RSA
import tornado
import os
from common.helpers import get_account_from_seed

"""
Example defender listens on port 4243 and uses account seed 2.
"""

account = get_account_from_seed(2)
print account

p1 = Player("127.0.0.1", 4243, account, "127.0.0.1", 10001)

tornado.ioloop.IOLoop.current().start()
