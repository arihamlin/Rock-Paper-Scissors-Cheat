#!/usr/bin/env python
import json
import hashlib


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


# class RSAPublicKey(BaseStructure):
#     name = "RSAPublicKey"
#     keys = ["n", "e"]


# class AccountIdentity(object):
#     @classmethod
#     def createFromPublicKey()


class SignedStructure(object):
    def __init__(self, payload, signature=None, key=None):
        assert payload
        self.payload = payload
        self.signature = signature
        self.pubkey = key

    def sign(self, key):
        self.signature = key.sign(self.payload.hash(), 0)
        self.pubkey = key.publickey()
        return self.signature

    def verifySignature(self, pubkey, sig=None):
        sig = sig or self.signature
        return pubkey.verify(self.payload.hash(), sig)

    def serialize(self):
        assert self.signature is not None
        return json.dumps({
                "payload": self.payload.serialize(),
                "signature": self.signature,
                "name": self.payload.name
            }, sort_keys=True)

    @classmethod
    def deserialize(self, bytes, pubkey=None):  # verifies signature
        obj = json.loads(bytes)
        assert "name" in obj
        assert "payload" in obj
        assert "signature" in obj

        # hack: find Structure class by name
        cls = globals()[obj["name"]]
        payload = cls.deserialize(obj["payload"])
        return SignedStructure(payload, obj["signature"])


class Payment(BaseStructure):
    name = "Payment"
    keys = ["from_account", "to_account", "amount"]


class InitiateEncounter(BaseStructure):
    name = "InitiateEncounter"
    keys = ["challenger", "defender", "begin_by", "end_by",
            "begin_at"]

class PostInitiateEncoutner(BaseStructure):
    name = "PostInitiateEncounter"
    keys = ["challenger", "defender", "begin_by", "end_by",
            "begin_at", "challenger_sign"]
    
class QueryState(BaseStructure):
    name = "QueryState"
    keys = ["account"]

class AccountState(BaseStructure):
    name = "AccountState"
    keys = ["account", "encounter_begin_at", "encounter_end_by",
            "in_encounter_with", "partial_chain_length",
            "stake", "balance"]

class CommitTransaction(BaseStructure):
    name = "Commitment"
    keys = ["prev", "commitment"]


class Resolution(BaseStructure):
    name = "Resolution"
    keys = ["prev"]


class CloseEncounter(BaseStructure):
    name = "CloseEncounter"
    keys = ["challenger", "defender", "moves"]


if __name__ == "__main__":
    import os
    import Crypto.PublicKey.RSA as RSA

    key = RSA.generate(KEY_SIZE, os.urandom)

    payment = Payment(from_account="from_account", to_account="to_account", amount=10)
    s = SignedStructure(payment)
    s.sign(key)

    serialized = s.serialize()
    deserialized = SignedStructure.deserialize(serialized)
    assert deserialized.verifySignature(key.publickey())
    assert payment == deserialized.payload

