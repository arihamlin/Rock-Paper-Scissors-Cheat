# Rock-Paper-Scissor-Cheat
###Changping Chen, Ariel Hamlin, Jeffrey Lim, Manushaqe Muco

### Components
This project is composed of 3 individually running components: relay, voter, and client. 

####Relay
Relay instantiates a TCP server that voters connect to. By keeping a list of connected voters, it can relay a message received from any voter to all other voters to simulate an idealized lossless peer-to-peer network. In current implementation, a client does not directly join the voter network, but instead posts and receives message from voters through a separate HTTP server interface on relay. To start a relay service, use the following command:
```
$ python voters/relay.py <p2p relay port> <http interface port>
```

Voter is a game proof verifier that records and maintains the global game state in a SQLite database. Each voter upon receiving game proof from clients through relay's HTTP interface, will validate the proof according to predefined rules and broadcast its validation result to other voters to reach consensus. Once a consensus is reached, the SQLite database representing the ledger is updated accordingly. A voter must have a valid account already existing on the ledger. To start a voter, run
```
$ python voters/voter.py <relay IP> <relay port> <account seed>
```

Client is a game player. It can behave as either challenger or defender. It runs a defender-mode TCP server that takes incoming connection from other client (challenger). It can also initiate connection to other client when it initiates a challenge. To start a client, initiate a "client.client_logic.Player" object. To begin a challenge, use "Player.start_encounter" function. 


### Implementation
All components take advantage of asynchronous network programming feature in Python Tornado library for rapid prototyping. It abstracts low-level TCP networking API in a event-based paradigm and greatly eases the implementation of communications between components. 

We represent users in our system using their unique public-keys. In addition, similar to Bitcoin network, we use a 48-character long account ID generated from the trailing 36 bytes of the hash of a user's public key encoded in DER format. This significantly reduces the length of an account ID, while preserving the one-to-one mapping between users and account IDs. However, when users sign a message, they must include their public key along with the signature since the verifier may not necessarily have the signer's public key for verification. The verifier must also check if the signer's account ID corresponds to the received public key. 

We use PyCrypto implementation for the cryptographic primitives, including RSA encryption and digital signatures. For hash functions, we use Python's built-in hashlib module.

Since no implementation for commitment scheme was readily available, we created our simple commitment scheme. In our design, a user concatenates the value to be committed with a 20-byte randomly generated padding, computes the SHA256 hash of the concatenated string as the commitment. To reveal the commitment, a user sends its committed value and previously generated padding to the verifier who computes the correct commitment the same way above and checks if it matches the previously received commitment. 

Such commitment scheme should be computationally binding unless the pseudorandom number generator is flawed or the collection-resistance property of underlying hash function is broken. The oneway-ness of the hash function guarantees computationally hiding property.

### Usage
##### Installing dependencies in a virtual environment
```
$ sudo apt-get install build-essential python-dev python-pip python-virtualenv
$ virtualenv --no-site-packages venv
$ . ./venv/bin/activate
$ pip install tornado bidict pycrypto enum34
```

##### Initialize example ledger
```
$ cp ledger-example.db ledger.db
```

##### Running components
In a minimal setup, we need to run one relay, one voter and two clients. 

```
# start a distributed network relay
$ . ./venv/bin/activate
$ python voters/relay.py 10000 10001
```

```
# start a voter
$ . ./venv/bin/activate
$ python voters/voter.py 127.0.0.1 10000 1
```

```
# start a defender 
$ . ./venv/bin/activate
$ python defender.py
```

```
# start a challenger 
$ . ./venv/bin/activate
$ python challenger.py
```
