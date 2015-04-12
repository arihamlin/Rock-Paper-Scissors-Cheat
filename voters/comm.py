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
import os
from bidict import bidict


def generate_node_id():
    return os.urandom(12).encode("base64").strip()

NODE_ID_LENGTH = 16

"""
P2PNetworkRelay is a TCP server that forwards message from one
client to all other clients. This is to simulate a stable 
decentralized peer-to-peer network.

VoterNode is a node on simulated P2P network and connects to a 
relay. 
"""

TYPE_BROADCAST = 1
TYPE_PEER_TO_PEER = 2


class P2PNetworkRelay(tornado.tcpserver.TCPServer):
    def __init__(self):
        tornado.tcpserver.TCPServer.__init__(self)
        self.nodes = bidict()  #  node : stream

    def print_totals(self):
        logging.info("%d voters online." % len(self.nodes))

    @tornado.gen.coroutine
    def handle_stream(self, stream, address):
        try:
            node_id = yield stream.read_bytes(NODE_ID_LENGTH)
        except tornado.iostream.StreamClosedError as e:
            print >> sys.stderr, e
            raise tornado.gen.Return()

        address = str(address)
        logging.info("Connected from " + node_id)

        self.nodes[node_id] = stream
        self.print_totals()

        try:
            while True:
                type_byte = yield stream.read_bytes(1)
                type = struct.unpack("!B", type_byte)[0]

                if type == TYPE_PEER_TO_PEER:
                    receiver_id = yield stream.read_bytes(NODE_ID_LENGTH)

                len_bytes = yield stream.read_bytes(2)
                length = struct.unpack("!H", len_bytes)[0]

                msg_bytes = yield stream.read_bytes(length)
                if type_byte == TYPE_PEER_TO_PEER:
                    node_stream = self.nodes[receiver_id:]
                    node_stream.write(len_bytes + node_id + msg_bytes)
                else:
                    for _, node_stream in self.nodes.iteritems():
                        if node_stream != stream:
                            node_stream.write(len_bytes + node_id + msg_bytes)
        except tornado.iostream.StreamClosedError as e:
            logging.info("Disconnected from " + node_id)
            if node_id in self.nodes:
                del self.nodes[node_id:]
            self.print_totals()


class VoterNode(object):
    def __init__(self, addr):
        self.server_addr = addr
        self.node_id = generate_node_id()
        tornado.ioloop.IOLoop.instance().add_callback(self.start)

    def close(self):
        self.stream.close()

    def on_close(self):
        tornado.ioloop.IOLoop.instance().stop()

    def broadcast_message(self, msg):
        data = json.dumps(msg)
        self.stream.write(struct.pack("!B", TYPE_BROADCAST))
        self.stream.write(struct.pack("!H", len(data)))
        self.stream.write(data)

    def send_message(self, receiver_id, msg):
        receiver_id = bytes(receiver_id)
        data = json.dumps(msg)
        self.stream.write(struct.pack("!B", TYPE_PEER_TO_PEER))
        assert len(receiver_id) == NODE_ID_LENGTH
        self.stream.write(receiver_id)
        self.stream.write(struct.pack("!H", len(data)))
        self.stream.write(data)

    @tornado.gen.coroutine
    def start(self):
        factory = tornado.tcpclient.TCPClient()
        try:
            self.stream = yield factory.connect(*self.server_addr)
            self.stream.write(self.node_id)
        except Exception as e:
            tornado.ioloop.IOLoop.instance().stop()
            print >> sys.stderr, e
            raise e
        logging.info("Connected to voter network with ID: %s" % self.node_id)

        self.on_connect()

        try:
            while True:
                len_bytes = yield self.stream.read_bytes(2)
                length = struct.unpack("!H", len_bytes)[0]
                from_bytes = yield self.stream.read_bytes(NODE_ID_LENGTH)
                msg_bytes = yield self.stream.read_bytes(length)
                msg = json.loads(msg_bytes)
                self.on_message(from_bytes, msg)
        except tornado.iostream.StreamClosedError as e:
            logging.info("Disconnected!")
            self.on_close()

