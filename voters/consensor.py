import tornado.ioloop
import tornado.log
import pickle
import ledger
import logging
from common.base import *
import hashlib
from verify import verify_encounter, verify_initiation


ROUND_TIME = 1500 # milliseconds
VOTING_THRESHOLDS = [0, 0, 0.5, 0.6, 0.7, 0.8]
FINAL_THRESHOLD = 0.8

NUMBER_OF_ROUNDS = len(VOTING_THRESHOLDS)
TRANSACTION_FEE = ledger.TRANSACTION_FEE

tornado.log.enable_pretty_logging()

class Consensor:
    def __init__(self, voter, account):
        self.voter = voter # The Voter instance that owns this
        self.account = account # Our own account in the ledger
        self.last_closed_ledger = ledger.Ledger("ledger_"+self.account.account_id[0:6]+".db") # Initialize from database on disk
        self.candidate_set = set() # Transactions that we're voting for
        self.deferral_set = set() # Transactions that didn't get enough votes, but will be considered for the next ledger
        self.round_number = 0 # Which stage we're in in the consensus process
        self.votes_heard = dict() # Votes that we've received so far (not including our own)
        self.timer = None

    # Tally up the votes, submit my proposal, and advance the round number
    def advance_round(self):
        threshold = VOTING_THRESHOLDS[self.round_number]
        if threshold == 0:
            logging.info("Listening for transactions...")
        else:
            logging.info("Advancing txs with >" + str(threshold) + " of the votes")

            # Count up the votes
            transaction_map = dict()
            tally = dict()
            total_stake = 0

            # Start with our own vote...
            our_candidate_set = set(self.candidate_set)
            #logging.info("OUR CANDIDATE SET:"+str([t.short_id() for t in our_candidate_set]))
            our_stake = self.last_closed_ledger.get_account_info(self.account.account_id)["stake"]
            total_stake += our_stake
            for tx in our_candidate_set:
                transaction_map[tx.id] = tx
                tally[tx.id] = our_stake

            # ...and then count the others
            for voter in self.votes_heard:
                their_candidate_set = self.votes_heard[voter]
                them = self.last_closed_ledger.get_account_info(voter)
                if not them:
                    logging.info("Voter has no stake; ignoring:"+voter)
                    continue
                their_stake = them["stake"]
                total_stake += their_stake
                for tx in their_candidate_set:
                    transaction_map[tx.id] = tx
                    if tx.id in tally: tally[tx.id] += their_stake
                    else: tally[tx.id] = their_stake

            # See which ones passed the threshold
            absolute_threshold = int(total_stake * threshold)
            new_candidate_set = set()
            for txid in tally:
                tx = transaction_map[txid]
                if tally[txid] >= absolute_threshold:
                    logging.info("Adding to candidate set tx "+tx.short_id())
                    new_candidate_set.add(tx)
                else:
                    logging.info("Not enough votes; deferring tx "+tx.short_id())
                    self.deferral_set.add(tx)
            self.candidate_set.clear()
            for t in new_candidate_set: self.candidate_set.add(t)

        # Submit my vote, or apply the final result.
        if self.round_number == NUMBER_OF_ROUNDS-1:
            self.finalize_ledger()
        else:
            self.send_voter_message({
                "proposal": pickle.dumps(self.candidate_set),
                "lcl_hash": self.last_closed_ledger.get_ledger_hash()
            })
            self.round_number += 1

    # Do this with all transactions that have reached the maximum threshold
    def finalize_ledger(self):
        final_proposal = set()
        total_fees = 0
        for tx in self.candidate_set:
            final_proposal.add(tx)
            if str(tx.__class__) != "consensor.CoinstakeSummary":
                total_fees += (2*TRANSACTION_FEE) #Don't include Coinstakes, since they don't pay fees
        
        # For each voter that we saw, defer a Coinstake transaction
        # so that they get their share of the transaction fees.
        if total_fees:
            self.votes_heard[self.account.account_id] = True
            for payee in self.votes_heard:
                css = CoinstakeSummary(
                    id = hashlib.sha256(payee + "" + self.last_closed_ledger.get_ledger_hash()).hexdigest(),
                    payee = payee,
                    total_fees = total_fees,
                    for_voting_on_changes_to_ledger_number = self.last_closed_ledger.get_ledger_root()["ledger_number"]
                )
                self.deferral_set.add(css)

        # Apply the transactions!
        self.last_closed_ledger.apply_transactions(final_proposal)

        # This round's deferrals become the next round's candidates, provided that they're still valid.
        self.candidate_set.clear()
        for tx in self.deferral_set:
            tx_type = str(tx.__class__)
            dv = False
            if tx_type == "consensor.InitiationSummary" and self.last_closed_ledger.is_valid_initiation_summary(tx):
                dv = True
            elif tx_type == "consensor.EncounterSummary" and self.last_closed_ledger.is_valid_encounter_summary(tx):
                dv = True
            elif tx_type == "consensor.CoinstakeSummary" and self.last_closed_ledger.is_valid_coinstake_summary(tx):
                dv = True

            if dv:
                logging.info("Deferral still valid for "+tx_type+" "+tx.short_id())
                self.candidate_set.add(tx)
            else:
                logging.info("Deferral no longer valid for "+tx_type+" "+tx.short_id())
                
        self.deferral_set.clear()
        self.votes_heard.clear()

        logging.info("Done with consensus round")
        self.start()

    # Add a transaction to the candidate set, and record our own vote on it (if it's not already in the candidate set)
    def consider_transaction(self, transaction):
        logging.info("Received transaction of type: "+transaction.payload.name)
        if transaction.payload.name == "PostInitiateEncounter":
            verification = verify_initiation(transaction.payload)
            if verification[0]: # If the transaction is internally valid
                summary = InitiationSummary(
                    id = str(transaction.signature),
                    challenger = verification[1],
                    defender = verification[2],
                    encounter_begin_by = verification[3],
                    encounter_end_by = verification[4]
                )
                if self.last_closed_ledger.is_valid_initiation_summary(summary): #If the transaction is externally valid
                    logging.info("Adding InitiateEncounter with id=" + summary.short_id() + " to candidate set")
                    if summary not in self.candidate_set:
                        self.candidate_set.add(summary)
                        self.relay_secondhand_transaction(transaction)
                else:
                    logging.info("Discarding InitiateEncounter transaction inconsistent with ledger")
        elif transaction.payload.name == "CloseEncounter":
            verification = verify_encounter(transaction.payload)
            if verification[0]: # If the transaction is internally valid
                summary = EncounterSummary(
                    id = str(transaction.signature),
                    winner = verification[1],
                    loser = verification[2],
                    was_tied = (verification[3] == "It was a tie!")
                )
                if self.last_closed_ledger.is_valid_encounter_summary(summary): # If the transaction is externally valid
                    logging.info("Adding CloseEncounter with id=" + summary.short_id() + " to candidate set")
                    if summary not in self.candidate_set:
                        self.candidate_set.add(summary)
                        self.relay_secondhand_transaction(transaction)
                else:
                    logging.info("Discarding CloseEncounter transaction inconsistent with ledger")
        else:
            logging.info("Discarding transaction of unknown type")

    # The first time we see a transaction, send it on to our peers so that they'll vote on it too
    def relay_secondhand_transaction(self, shtx):
        logging.info("Relaying secondhand")
        self.send_voter_message({
            "secondhand": SignedStructure.serialize(shtx)
        })

    # Send a message to the other voters
    def send_voter_message(self, msg):
        self.voter.send_voter_message(msg)

    # Whenever we get a message from another voter
    def process_voter_message(self, sender_id, msg):
        if "proposal" in msg: # It's a vote
            sender_account_id = msg["account_id"]
            their_proposal = pickle.loads(msg["proposal"])
            # At this point we should check to make sure that the signature on the message is genuine.
            # Also, check to see that they're talking about the same ledger as we are.
            if self.last_closed_ledger.get_ledger_hash() == msg["lcl_hash"]:
                self.votes_heard[sender_account_id] = their_proposal
            else:
                logging.info("Ignoring vote for non-current ledger "+msg["lcl_hash"][0:9]+"...")
        elif "secondhand" in msg:
            shtx = SignedStructure.deserialize(msg["secondhand"])
            self.consider_transaction(shtx)
        else:
            logging.info("Could not understand voter message; dropping: "+str(msg))

    # Start a consensus round
    def start(self):
        logging.info("Starting new consensus round")
        my_info = self.last_closed_ledger.get_account_info(self.account.account_id)
        if not my_info:
            logging.error("Account does not exist: "+self.account.account_id)
            return

        if self.timer: self.timer.stop()
        self.round_number = 0
        self.timer = tornado.ioloop.PeriodicCallback(self.advance_round, ROUND_TIME)
        self.timer.start()

    def stop(self):
        if self.timer: self.timer.stop()


# Helper classes to represent "transaction summaries".
# These describe how a transaction will affect the ledger, but don't carry any signatures.
class Summary:
    def __init__(self):
        pass #Override this in subclasses
    def short_id(self):
        return self.id[1:9] + "..."
    def __hash__(self):
        return self.id.__hash__()
    def __eq__(self, other):
        return self.id == other.id
    def __ne__(self, other):
        return (not self.__eq__(other))

class InitiationSummary(Summary):
    def __init__(self, id, challenger, defender, encounter_begin_by, encounter_end_by):
        self.id = id
        self.challenger = challenger
        self.defender = defender
        self.encounter_begin_by = encounter_begin_by
        self.encounter_end_by = encounter_end_by

class EncounterSummary(Summary):
    def __init__(self, id, winner, loser, was_tied):
        self.id = id
        self.winner = winner
        self.loser = loser
        self.was_tied = was_tied
    def __str__(self):
        return str({
            "id": self.id,
            "winner": self.winner,
            "loser": self.loser,
            "was_tied": self.was_tied
        })

class CoinstakeSummary(Summary):
    def __init__(self, id, payee, total_fees, for_voting_on_changes_to_ledger_number):
        self.id = id
        self.payee = payee
        self.total_fees = total_fees
        self.for_voting_on_changes_to_ledger_number = for_voting_on_changes_to_ledger_number




if __name__ == "__main__":
    def main():
        c = Consensor(ledger.GENESIS_ACCOUNT_ID)
        c.start()

    tornado.ioloop.IOLoop.instance().add_callback(main)
    tornado.ioloop.IOLoop.instance().start()
