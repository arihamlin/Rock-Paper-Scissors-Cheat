import sys, os.path
sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), os.pardir))
from common.base import SignedStructure

def verify_encounter(encounter):
    # returns (verification result, winner, msg)
    challenger, defender = encounter.challenger, encounter.defender
    moves = encounter.moves.split("#")

    move_types = ['CommitTransaction', 'CommitTransaction',
        'RevealTransaction', 'RevealTransaction', 'CommitTransaction',
        'CommitTransaction', 'RevealTransaction', 'RevealTransaction',
        'CommitTransaction', 'CommitTransaction', 'RevealTransaction',
        'RevealTransaction', 'Resolution']


    for idx, encoded_move in enumerate(moves):
        move = SignedStructure.deserialize(encoded_move)

        # Received move must be signed by either defender
        # or challenger. If it is not, the poster should
        # not have sent it to voters in the beginning.
        if idx % 2 == 0:  # from defender
            if not move.verifySignature(defender):
                msg = "Move #%i not signed by defender." % idx
                return (False, None, msg)
        else:
            if not move.verifySignature(challenger):
                msg = "Move #%i not signed by challenger." % idx
                return (False, None, msg)

        if idx > 1:
            prev_move = SignedStructure.deserialize(moves[idx - 1])
            if prev_move.signature != move.payload.prev:
                msg = "Move #%i does not have correct previous signature." % idx
                return (False, None, msg)

        if move.payload.name != move_types[idx]:
            msg = "Move #%i should be %s." % (idx, move_types[idx])
                return (False, None, msg)

    return (True, challenger, None)

if __name__ == "__main__":
    f = open("encounter.p", "rb")
    import pickle
    req = pickle.load(f)
    signed = SignedStructure.deserialize(req)
    print verify_encounter(signed.payload)

