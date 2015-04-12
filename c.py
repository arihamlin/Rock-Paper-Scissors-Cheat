from client.client_logic import Player
import Crypto.PublicKey.RSA as RSA
import os
import tornado

key = RSA.generate(1024, os.urandom)
p1 = Player("127.0.0.1", 4242, key)

def main():
	p1.start_encounter("127.0.0.1", 4243, "xxxx")

tornado.ioloop.IOLoop.current().add_callback(main)
tornado.ioloop.IOLoop.current().start()
