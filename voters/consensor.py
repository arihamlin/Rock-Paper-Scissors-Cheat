import tornado.ioloop
import tornado.log
import ledger
import logging
from verify import verify_encounter, verify_initiation

ROUND_TIME = 1000 # milliseconds
VOTING_THRESHOLDS = [0, 0, 0.5, 0.6, 0.7, 0.8]
FINAL_THRESHOLD = 0.8
NUMBER_OF_ROUNDS = len(VOTING_THRESHOLDS)
TRANSACTION_FEE = ledger.TRANSACTION_FEE

tornado.log.enable_pretty_logging()

class InitiationSummary:
    def __init__(self, id, challenger, defender, encounter_end_by): #etc
        self.id = id
        self.challenger = challenger
        self.defender = defender
        self.encounter_end_by = encounter_end_by
    def short_id(self):
        return self.id[1:9] + "..."
        
class EncounterSummary:
    def __init__(self, id, winner, loser, was_tied):
        self.id = id
        self.winner = winner
        self.loser = loser
        self.was_tied = was_tied
    def short_id(self):
        return self.id[1:9] + "..."
    def __str__(self):
        return str({
            "id": self.id,
            "winner": self.winner,
            "loser": self.loser,
            "was_tied": self.was_tied
        })

class CoinstakeSummary:
    def __init__(self, id, payee, total_fees):
        self.id = id
        self.payee = payee
        self.total_fees = total_fees


class Consensor:
    def __init__(self, account):
        self.account = account # Our own account in the ledger
        self.last_closed_ledger = ledger.Ledger("ledger.db") # Initialize from database on disk
        self.candidate_set = set() # Transactions that we're voting for
        self.deferral_set = set() # Transactions that didn't get enough votes, but will be considered for the next ledger
        self.round_number = 0 # Which stage we're in in the consensus process
        self.timer = None

    # Tally up the votes, submit my proposal, and advance the round number
    def advance_round(self):
        threshold = VOTING_THRESHOLDS[self.round_number]
        if threshold == 0:
            logging.info("Listening for transactions...")
        else:
            logging.info("Advancing txs with >" + str(threshold) + " votes")
            # update candidate_set; defer txs with insufficient votes
        if self.round_number == NUMBER_OF_ROUNDS-1:
            self.finalize_ledger(threshold)
        else:
            # submit my votes
            self.round_number += 1


    def finalize_ledger(self, threshold):
        #return
        final_proposal = set()
        #deferrals = set()

        for tx in self.candidate_set:
            if True: #If it passes the threshold
                final_proposal.add(tx)
            else:
                self.deferral_set.add(tx)

        # For each voter that we saw, defer a Coinstake transaction
        # so that they get their share of the transaction fees.

        """
        rewardable_voters = list()
        rewardable_stake = 0
        for voter in self.voters_seen:
            if True: #If voter deserves reward:
                stake = self.voters_seen[voter]
                rewardable_voters.append({
                    "voter_id": voter,
                    "stake": stake,
                })
                rewardable_stake += stake

        # Determine reward by the "House of Representatives" method, breaking ties alphabetically
        transaction_count = len(final_proposal) # TODO: exclude coinstake transactions
        reward_per_stake = float(transaction_count*TRANSACTION_FEE)/rewardable_stake
        unallocated_reward = transaction_count*TRANSACTION_FEE
        for rv in rewardable_voters:
            reward = rv["stake"] * reward_per_stake
            rv["reward"] = reward
            rv["integer_reward"] = int(reward)
            unallocated_reward -= int(reward)
        rewardable_voters.sort(key=lambda x: x["voter_id"])
        rewardable_voters.sort(key=lambda x: -x["reward"])
        for rv in rewardable_voters:
            if unallocated_reward:
                rv["integer_reward"] += 1
                unallocated_reward -= 1
            else:
                break

        for rv in rewardable_voters:
            coinstake = None #A tx to give rv["voter_id"] rv["integer_reward"]
            deferrals.add(coinstake)
        """

        # This round's deferrals become the next round's candidates
        self.candidate_set = self.deferral_set
        self.deferral_set = set()

        self.last_closed_ledger.apply_transactions(final_proposal)

        self.start()

    # Add transaction to the candidate set, and record my own vote on it (if it's not already in the candidate set)
    def consider_transaction(self, transaction):
        logging.info("Received transaction of type: "+transaction.payload.name)
        if transaction.payload.name == "PostInitiateEncounter":
            verification = verify_initiation(transaction.payload)
            if verification[0]: #If the transaction is internally valid
                summary = InitiationSummary(
                    id = str(transaction.signature),
                    challenger = verification[1],
                    defender = verification[2],
                    encounter_end_by = verification[3]
                )
                if self.last_closed_ledger.is_valid_initiation_summary(summary): #If the transaction is externally valid
                    logging.info("Adding InitiateEncounter with id=" + summary.short_id() + "... to candidate set")
                    self.candidate_set.add(summary)
                else:
                    logging.info("Discarding InitiateEncounter transaction inconsistent with ledger")
        elif transaction.payload.name == "CloseEncounter":
            verification = verify_encounter(transaction.payload)
            #logging.info("Verification: "+str(verification))
            if verification[0]: #If the transaction is internally valid
                summary = EncounterSummary(
                    id = str(transaction.signature),
                    winner = verification[1],
                    loser = verification[2],
                    was_tied = (verification[3] == "It was a tie!")
                )
                if self.last_closed_ledger.is_valid_encounter_summary(summary): #If the transaction is externally valid
                    logging.info("Adding CloseEncounter with id=" + summary.short_id() + "... to candidate set")
                    self.candidate_set.add(summary)
                else:
                    logging.info("Discarding CloseEncounter transaction inconsistent with ledger")
        else:
            logging.info("Discarding transaction of unknown type")


    # Update the vote tally based on an incoming proposal
    def receive_proposal(self, proposal):
        pass
        #Update voters_seen and total_stake, if necessary

    # Check if a transaction is consistent with the LCL and the CS
    def would_be_valid(self, transaction):
        return True

    def start(self):
        logging.info("Starting new consensus round")
        self.voters_seen = dict() #key=voter id, value = stake in LCL
        my_info = self.last_closed_ledger.get_account_info(self.account.account_id)
        if not my_info:
            logging.error("Account does not exist: "+self.account.account_id)
            return
        my_stake = my_info["stake"]
        self.voters_seen[self.account.account_id] = my_stake
        self.total_stake = my_stake

        if self.timer: self.timer.stop()
        self.round_number = 0
        self.timer = tornado.ioloop.PeriodicCallback(self.advance_round, ROUND_TIME)
        self.timer.start()

    def stop(self):
        if self.timer: self.timer.stop()


"""
class Consensor:
    def __init__(self, account):
        self.account.account_id = account
        self.periodic = None
        self.round_number = 0
        self.candidate_set = set()
        self.rejection_set = set()
        self.deferral_set = set()
        self.seen_transactions = set()
        self.last_closed_ledger = None #Read from database

    def consider_transaction(self, tx):
        pass
        # Is the transaction validly formed and signed?
        if not tx.is_valid():
            reject_transaction(tx)
        if not is_consistent(tx, last_closed_ledger, candidate_set):
            reject_transaction(tx)
        else:
            accept_transaction(tx)




    def reject_transaction(self, tx):
        self.rejection_set.add(tx)
        self.publish_vote(tx, False, 0)

    def accept_transaction(self, tx):
        self.candidate_set.add(tx)
        self.publish_vote(tx, True, 0)

    # tx = the transaction we're voting on
    # vote = True or False, we're voting yes or no
    # round = integer, the round number we're voting on (0, 1, 2, 3)
    def publish_vote(self, tx, vote, round):
        pass

    def update_round_number(self):
        self.round_number = (self.round_number + 1) % 4

    def start(self):
        if self.periodic: self.periodic.stop()
        self.round_number = 0
        self.periodic = tornado.ioloop.PeriodicCallback(self.update_round_number, 1000)
        self.periodic.start()
        # listen for transactions, and vote; listen for round 0 votes
        # listen for round 1 votes
        # listen for round 2 votes
        # listen for round 3 votes
        # sign final set, broadcast, and update ledger

    def process_transaction(self, tx):
        if self.round_number == 0:
            self.consider_transaction(tx)
        elif self.round_number == 1:
            pass
        elif self.round_number == 2:
            pass
        elif self.round_number == 3:
            pass
"""

def is_consistent(transaction, ledger, candidates):
    return True

if __name__ == "__main__":
    def main():
        c = Consensor(ledger.GENESIS_ACCOUNT_ID)
        c.start()

    tornado.ioloop.IOLoop.instance().add_callback(main)
    tornado.ioloop.IOLoop.instance().start()
