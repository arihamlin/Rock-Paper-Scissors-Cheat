# pip install tornado

import sys
import json
import tornado.tcpserver
import tornado.ioloop
import tornado.gen
import tornado.log
import logging
import tornado.web
import tornado.tcpclient
import struct
import random
import os
from bidict import bidict


def generate_node_id():
    return os.urandom(12).encode("base64").strip()

NODE_ID_LENGTH = 16

"""
# Classes:

P2PNetworkRelay is a TCP server that forwards message from one
voter to all other voters. This is to simulate a stable 
decentralized peer-to-peer network.

VoterNode is a node on simulated P2P network and connects to a 
relay. It provides a "on_message" callback used by Voter.

VoterInterfaceProxy is an HTTP server that forwards messages
received from clients to specifide number of voters. It has
an option of waiting for a number of responses. Clients use
this interface to query AccountState from voters and post
game result. Check voter_interface_ex.py for usage.

# Implementation details

"Node ID" is independent of account ID. It's used by Relay to
identity individual nodes on the network. It's randomly generated
when nodes connect to relay.

Messages passed in the simulated P2P network are prefixed by
their (1) message type (one-byte constant below) and size 
(two-bytes big-endian fixed header). 
"""

TYPE_BROADCAST = 1
TYPE_PEER_TO_PEER = 2


class P2PNetworkRelay(tornado.tcpserver.TCPServer):
    def __init__(self):
        tornado.tcpserver.TCPServer.__init__(self)
        self.nodes = bidict()  #  node : stream
        self.proxy_callbacks = dict()

    def send_message(self, nnodes, msg, callback):
        assert nnodes <= len(self.nodes)
        node_id = generate_node_id()
        if callback:
            self.proxy_callbacks[node_id] = callback
        data = json.dumps({
            "request": msg.encode("base64"),
            "event": "client_request"
        })
        items = self.nodes.items()
        random.shuffle(items)
        for _, stream in items[:nnodes]:
            stream.write(struct.pack("!H", len(data)))
            stream.write(node_id)
            stream.write(data)

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
                if type == TYPE_PEER_TO_PEER:
                    if receiver_id in self.nodes:
                        node_stream = self.nodes[receiver_id:]
                        node_stream.write(len_bytes + node_id + msg_bytes)
                    elif receiver_id in self.proxy_callbacks:
                        self.proxy_callbacks[receiver_id](msg_bytes)
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

    def remove_callback(self, node_id):
        if node_id in self.proxy_callbacks:
            del self.proxy_callbacks[node_id]


class VoterInterfaceProxy(tornado.web.RequestHandler):
    def initialize(self, relay):
        self.relay = relay
        self.resp = []
        self.nresponses = 0
        self.node_id = None

    def prepare(self):
        pass

    def on_msg(self, data):
        msg = json.loads(data)
        self.resp.append(msg["result"])
        if len(self.resp) >= self.nresponses:
            self.finish({"responses": self.resp})

    def on_finish(self):
        if self.node_id:
            self.relay.remove_callback(self.node_id)

    @tornado.web.asynchronous
    def post(self):
        # nnodes = number of voter nodes to forward client's request
        # nresponses = number of responses to wait from voters
        nnodes = int(self.get_argument("nnodes", 1))
        self.nresponses = int(self.get_argument("nresponses", 0))
        if self.nresponses == 0:
            self.relay.send_message(nnodes, self.request.body, None)
            self.finish()
        else:
            self.node_id = self.relay.send_message(nnodes,
                self.request.body, self.on_msg)
