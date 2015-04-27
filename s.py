from client.client_logic import Player
import Crypto.PublicKey.RSA as RSA
import tornado
import os

key = RSA.generate(1024, os.urandom)
p1 = Player("127.0.0.1", 4243, key, "127.0.0.1", 10001)

tornado.ioloop.IOLoop.current().start()
