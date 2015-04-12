#!/usr/bin/env python
import sys, os.path
sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), os.pardir))

import json
import hashlib
import os
import Crypto.PublicKey.RSA as RSA


KEY_SIZE = 2048


class BaseStructure(object):
    name = "BaseStructure"
    keys = list()

    def __init__(self, **kwargs):
        self.data = dict()

        for k,v in kwargs.iteritems():
            assert k in self.keys
            self.data[k] = v

    def validate(self):
        for k in self.keys:
            assert k in self.keys
        return True

    def serialize(self):
        assert self.validate()
        return json.dumps(self.data, sort_keys=True)

    @classmethod
    def deserialize(cls, bytes):
        obj = json.loads(bytes)
        return cls(**obj)

    def hash(self):
        return hashlib.sha256(self.serialize()).hexdigest()

    def verifyHash(self, h):
        return h == self.hash()

    def __eq__(self, other):
        if self.name != other.name:
            return False
        for k in self.keys:
            if self.data.get(k) != other.data.get(k):
                return False
        return True


class AccountIdentity(BaseStructure):
    name = "AccountIdentity"
    keys = ["account_id", "public_key"]

    def __init__(self, account_id=None, key=None, public_key=None):
        self.account_id = account_id
        if public_key:
            self.public_key = self.decodePublicKey(public_key)
        else:
            self.public_key = key.publickey()
        self.key = key

        if self.account_id is None and self.public_key is not None:
            self.account_id = AccountIdentity.findAccountName(self.public_key)

        BaseStructure.__init__(self, account_id=self.account_id,
            public_key=self.encodePublicKey(self.public_key))

    def decodePublicKey(self, encoded):
        return RSA.importKey(encoded.decode("base64"))

    def encodePublicKey(self, public_key):
        return public_key.exportKey(format="DER").encode("base64").strip()

    @classmethod
    def findAccountName(cls, public_key):
        return hashlib.sha1(public_key.exportKey(format="DER")).hexdigest()

    def hasPrivateKey(self):
        return self.key.has_private()

    def sign(self, M):
        return self.key.sign(M, 0)

    def verifySignature(self, M, sig):
        if self.account_id != AccountIdentity.findAccountName(self.public_key):
            return False
        return self.public_key.verify(M, sig)

    def __repr__(self):
        return "Account<%s>" % self.account_id


class SignedStructure(object):
    def __init__(self, payload, account=None, signature=None):
        assert payload
        self.account = account
        self.payload = payload
        self.signature = signature

    def sign(self, account):
        self.account = account
        self.signature = account.sign(self.payload.hash())
        return self.signature

    def verifySignature(self, account_id):
        if account_id != self.account.account_id:
            return False
        return self.account.verifySignature(self.payload.hash(), self.signature)

    def serialize(self):
        assert self.signature is not None
        return json.dumps({
                "payload": self.payload.serialize(),
                "signature": self.signature,
                "account": self.account.serialize(),
                "name": self.payload.name
            }, sort_keys=True)

    @classmethod
    def deserialize(self, bytes):  
        obj = json.loads(bytes)
        assert "name" in obj
        assert "payload" in obj
        assert "signature" in obj
        assert "account" in obj

        # hack: find Structure class by name
        cls = globals()[obj["name"]]
        payload = cls.deserialize(obj["payload"])
        account = AccountIdentity.deserialize(obj["account"])
        return SignedStructure(payload, signature=obj["signature"], account=account)


class Commitment(BaseStructure):
    name = "Commitment"
    keys = ["input", "hash"]
    secret = None

    def computeCommitment(self, input, secret):
        assert secret is not None
        return hashlib.sha256(input + secret).hexdigest()

    def getSecret(self):
        return self.secret

    def serialize(self):
        if "hash" not in self.data:
            self.secret = os.urandom(20)
            self.data["hash"] = computeCommitment(self.data["input"], self.secret)
        return BaseStructure.serialize(self)

    @classmethod
    def deserialize(cls, bytes):
        obj = BaseStructure.deserialize(cls, bytes)

    def verifyCommitment(self, secret):
        assert "hash" in self.data
        return self.data["hash"] == computeCommitment(self.data["input"], self.secret)


class Payment(BaseStructure):
    name = "Payment"
    keys = ["from_account", "to_account", "amount"]


class InitiateEncounter(BaseStructure):
    name = "InitiateEncounter"
    keys = ["challenger", "defender", "begin_by", "end_by"]

class PostInitiateEncounter(BaseStructure):
    name = "PostInitiateEncounter"
    keys = ["challenger", "defender", "begin_by", "end_by",
             "challenger_sign"]

class QueryState(BaseStructure):
    name = "QueryState"
    keys = ["account"]

class AccountState(BaseStructure):
    name = "AccountState"
    keys = ["account", "encounter_begin_at", "encounter_end_by",
            "in_encounter_with", "partial_chain_length",
            "stake", "balance"]

class CommitTransaction(BaseStructure):
    name = "CommitTransaction"
    keys = ["prev", "commitment"]

class RevealTransaction(BaseStructure):
    name = "RevealTransaction"
    keys = ['prev','value']
    
class Resolution(BaseStructure):
    name = "Resolution"
    keys = ["prev"]


class CloseEncounter(BaseStructure):
    name = "CloseEncounter"
    keys = ["challenger", "defender", "moves"]


if __name__ == "__main__":
    import os

    key = RSA.generate(KEY_SIZE, os.urandom)
    account = AccountIdentity(key=key)
    print account

    payment = Payment(from_account=account.account_id,
        to_account="to_account", amount=10)
    s = SignedStructure(payment)
    s.sign(account)

    serialized = s.serialize()
    deserialized = SignedStructure.deserialize(serialized)
    assert deserialized.verifySignature(account.account_id)
    assert payment == deserialized.payload

