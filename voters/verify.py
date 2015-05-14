import sys, os.path
sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), os.pardir))
from common.base import SignedStructure, Commitment
import base64
import logging

def verify_initiation(initiation):
    logging.info("verify_initiation:"+str(initiation))
    #<challenger=u'OTMwMmRhMzIwNTYwYmZmZmUzYzAwNzFiYjlmNGNiM2NkM2Vh', defender=u'xxxx', begin_by=2, end_by=602, challenger_sign=[123]>
    challenger = initiation.challenger
    defender = initiation.defender
    encounter_begin_by = initiation.begin_by
    encounter_end_by = initiation.end_by
    if False: #If the signature verification fails
        return (False, None, None, None, None)
    else:
        return (True, challenger, defender, encounter_begin_by, encounter_end_by)

def verify_encounter(encounter):
    # returns (verification result, winner, loser, msg)
    challenger, defender = encounter.challenger, encounter.defender

    move_types = ['CommitTransaction', 'CommitTransaction',
        'RevealTransaction', 'RevealTransaction', 'CommitTransaction',
        'CommitTransaction', 'RevealTransaction', 'RevealTransaction',
        'CommitTransaction', 'CommitTransaction', 'RevealTransaction',
        'RevealTransaction', 'Resolution']

    moves = []
    signed_moves = []
    for idx, encoded_move in enumerate(encounter.moves.split("#")):
        move = SignedStructure.deserialize(encoded_move)
        signed_moves.append(move)
        moves.append(move.payload)

        # Received move must be signed by either defender
        # or challenger. If it is not, the poster should
        # not have sent it to voters in the beginning.
        if idx % 2 == 0:  # from defender
            if not move.verifySignature(defender):
                msg = "Move #%i not signed by defender." % idx
                return (False, None, None, msg)
        else:
            if not move.verifySignature(challenger):
                msg = "Move #%i not signed by challenger." % idx
                return (False, None, None, msg)

        if idx > 1:
            if signed_moves[idx - 1].signature != move.payload.prev:
                msg = "Move #%i does not have correct previous signature." % idx
                return (False, None, None, msg)

        if move.payload.name != move_types[idx]:
            msg = "Move #%i should be %s." % (idx, move_types[idx])
            return (False, None, None, msg)

    round_idx = 0
    def compute_round_result(round_idx):
        defender_commitment = Commitment.deserialize(moves[round_idx].commitment)
        challenger_commitment = Commitment.deserialize(moves[round_idx+1].commitment)
        defender_reveal = moves[round_idx+2]
        challenger_reveal = moves[round_idx+3]

        if not defender_commitment.verifyCommitment(base64.b64decode(defender_reveal.secret),
            defender_reveal.value):
            msg = "Defender's commitment verification failed."
            return (False, None, None, msg)

        if not challenger_commitment.verifyCommitment(base64.b64decode(challenger_reveal.secret),
            challenger_reveal.value):
            msg = "Challenger's commitment verification failed."
            return (False, None, None, msg)

        defender_move = defender_reveal.value
        challenger_move = challenger_reveal.value

        assert defender_move in ["R", "P", "S"]
        assert challenger_move in ["R", "P", "S"]

        if ((defender_move == "P" and challenger_move == "R") or
            (defender_move == "R" and challenger_move == "S") or
            (defender_move == "S" and challenger_move == "P")):
            return (1, 0)
        elif defender_move == challenger_move:
            return (0, 0)
        else:
            return (0, 1)

    r1 = compute_round_result(0)
    if r1[0] is False:
        return r1
    r2 = compute_round_result(4)
    if r2[0] is False:
        return r2
    r3 = compute_round_result(8)
    if r3[0] is False:
        return r3

    result = (r1[0] + r2[0] + r3[0], r1[1] + r2[1] + r3[1])

    if result[0] == result[1]:
        return (True, challenger, defender, "It was a tie!") #Do not change this string

    if result[0] > result[1]:
        return (True, defender, challenger, "Defender wins!")

    if result[0] < result[1]:
        return (True, challenger, defender, "Challenger wins!")


if __name__ == "__main__":
    f = open("encounter.p", "rb")
    import pickle
    req = pickle.load(f)
    signed = SignedStructure.deserialize(req)
    print verify_encounter(signed.payload)

