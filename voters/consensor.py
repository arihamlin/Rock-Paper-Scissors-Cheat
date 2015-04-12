import tornado

ROUND_TIME = 1000 # milliseconds
VOTING_THRESHOLDS = [0.5, 0.6, 0.7]
FINAL_THRESHOLD = 0.8
NUMBER_OF_ROUNDS = len(VOTING_THRESHOLDS)
TRANSACTION_FEE = 360


class Consensor:
    def __init__(self, account_id, private_key):
        self.account_id = account_id
        self.private_key = private_key
        self.timer = None
        self.last_closed_ledger = None #initialize from database
        self.candidate_set = dict() #key=transaction, value=set of votes


    # Tally up the votes, submit my proposal, and advance the round number
    def advance_round(self):
        threshold = VOTING_THRESHOLDS[min(NUMBER_OF_ROUNDS, self.round_number)]
        pass
        if False: #If every tx passes FINAL_THRESHOLD
            self.finalize_ledger()
        else:


    def finalize_ledger(self):
        final_proposal = set()
        deferrals = set()

        for tx in self.candidate_set:
            if True: #If it passes the threshold
                final_proposal.add(tx)
            else:
                deferrals.add(tx)

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

        self.candidate_set = deferrals
        self.last_closed_ledger.apply_transactions(final_proposal)

        self.start()

    # Add transaction to the candidate set, and record my own vote on it (if it's not already in the candidate set)
    def receive_transaction(self, transaction):
        if transaction not in self.candidate_set:
            self.candidate_set[transaction] = set()
            if self.would_be_valid(transaction):
                self.candidate_set[transaction].add(self.account_id)

    # Update the vote tally based on an incoming proposal
    def receive_proposal(self, proposal):
        pass
        #Update voters_seen and total_stake, if necessary

    # Check if a transaction is consistent with the LCL and the CS
    def would_be_valid(self, transaction):
        return True

    def start(self):
        self.voters_seen = dict() #key=voter id, value = stake in LCL
        my_stake = self.last_closed_ledger.get_account_info(account_id)["stake"]
        self.voters_seen[account_id] = my_stake
        self.total_stake = my_stake

        if self.timer: self.timer.stop()
        self.round_number = 0
        self.timer = tornado.ioloop.PeriodicCallback(self.advance_round, ROUND_TIME)
        self.timer.start()




class Consensor:
    def __init__(self, account_id, private_key):
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


def is_consistent(transaction, ledger, candidates):
    return True
