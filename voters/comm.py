# pip install tornado

import sys
import json
import tornado.tcpserver
import tornado.ioloop
import tornado.gen
import tornado.log
import logging
import tornado.tcpclient
import struct


"""
P2PNetworkRelay is a TCP server that forwards message from one
client to all other clients. This is to simulate a stable 
decentralized peer-to-peer network.

VoterNode is a node on simulated P2P network and connects to a 
relay. 
"""


class P2PNetworkRelay(tornado.tcpserver.TCPServer):
    def __init__(self):
        tornado.tcpserver.TCPServer.__init__(self)
        self.voters = set()

    def print_totals(self):
        logging.info("%d voters online." % len(self.voters))

    @tornado.gen.coroutine
    def handle_stream(self, stream, address):
        address = str(address)
        logging.info("Connected from " + address)

        self.voters.add(stream)
        self.print_totals()

        try:
            while True:
                len_bytes = yield stream.read_bytes(2)
                length = struct.unpack("!H", len_bytes)[0]
                msg_bytes = yield stream.read_bytes(length)

                closed_streams = []
                for voter in self.voters:
                    if voter != stream:
                        voter.write(len_bytes)
                        voter.write(msg_bytes)
        except tornado.iostream.StreamClosedError as e:
            logging.info("Disconnected from " + address)
            self.voters.remove(stream)
            self.print_totals()



class VoterNode(object):
    def __init__(self, addr):
        self.server_addr = addr
        tornado.ioloop.IOLoop.instance().add_callback(self.start)

    def close(self):
        self.stream.close()

    def on_close(self):
        tornado.ioloop.IOLoop.instance().stop()

    def broadcast_message(self, msg):
        data = json.dumps(msg)
        self.stream.write(struct.pack("!H", len(data)))
        self.stream.write(data)

    @tornado.gen.coroutine
    def start(self):
        factory = tornado.tcpclient.TCPClient()
        try:
            self.stream = yield factory.connect(*self.server_addr)
        except Exception as e:
            tornado.ioloop.IOLoop.instance().stop()
            print >> sys.stderr, e
            raise e
        logging.info("Connected to voter network!")

        self.on_connect()

        try:
            while True:
                len_bytes = yield self.stream.read_bytes(2)
                length = struct.unpack("!H", len_bytes)[0]
                msg_bytes = yield self.stream.read_bytes(length)
                msg = json.loads(msg_bytes)
                self.on_message(msg)
        except tornado.iostream.StreamClosedError as e:
            logging.info("Disconnected!")
            self.on_close()

