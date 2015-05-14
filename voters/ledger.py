import sqlite3
import logging
import hashlib

GENESIS_ACCOUNT_ID = "ZDRlNjg0ZDgyOGEyYTY5ZjY4MDYxZjhiYzZiYzFjNjJmZjlj" # This is the account with seed=1.
TRANSACTION_FEE = 360


def dict_factory(cursor, row):
	d = {}
	for idx, col in enumerate(cursor.description):
		d[col[0]] = row[idx]
	return d

"""
The ledger contains entries with the following fields:
account_id: String, the hash of the public key
stake: Integer, how much money they have
skill: Integer, their skill (ELO) rating
in_encounter_with: String, who they're in an encounter with (optional)
encounter_begin_at: Integer, when that encounter started (optional)
encounter_end_by: Integer, when that encounter is to end by (optional)
partial_chain_length: Integer, the length of an incomplete encounter (optional)

The ledger root contains:
merkle_root: String, the hash of all the ledger entries
ledger_number: Integer, the incrementing count of the ledgers
previous_hash: String, the hash of the previous ledger

The ledger hash is the hash of the ledger root. (Signatures are computed off of this.)
"""
class Ledger():

	# Initialize ledger from database file; if there is no such file, create it.
	def __init__(self, db):
		try:
			f = open(db)
			f.close()
			exists = True
		except IOError:
			exists = False

		self.conn = sqlite3.connect(db)
		self.conn.row_factory = dict_factory

		if not exists:
			initalize_database(self.conn)
			self.make_genesis()

	def make_genesis(self):
		c = self.conn.cursor()
		print "Making genesis"
		c.execute("INSERT INTO ledger_main (account_id, stake, skill) VALUES (?,?,?)", (
			GENESIS_ACCOUNT_ID, # Genesis account ID
			360000000000, # stake
			0 # skill
		))
		c.execute("INSERT INTO ledger_root VALUES (?,?,?)", ("", 0, ""))
		c.execute("INSERT INTO ledger_hash VALUES (?)", ("",))
		self.conn.commit()
		self.update_root_and_hash()

	# Is a given InitiateEncounter summary valid, with respect to this ledger?
	def is_valid_initiation_summary(self, summary):
		# If they can afford the transaction fees,
		# they're not already in encounters,
		# and it's not too early or late.
		# However, even if one or both players ARE in encounters,
		# they can start a new encounter regardless as long as both "end_by" dates have expired.

		challenger = self.get_account_info(summary.challenger)
		defender = self.get_account_info(summary.defender)
		if challenger["stake"] < TRANSACTION_FEE or defender["stake"] < TRANSACTION_FEE:
			return False
		if ((challenger["in_encounter_with"] and challenger["encounter_end_by"]>challenger["current_ledger"]) or 
			(defender["in_encounter_with"]) and defender["encounter_end_by"]>defender["current_ledger"]):
			return False
		if challenger["current_ledger"] > summary.encounter_begin_by:
			return False
		if challenger["current_ledger"] > summary.encounter_end_by:
			return False
		return True

	# Is a given encounter summary valid?
	def is_valid_encounter_summary(self, summary):
		# Verify:
		# 1. that both players can afford the transaction fee
		# 2. that they're currently in an encounter with each other
		# 3. that it's not too early
		# 4. that it's not too late
		winner = self.get_account_info(summary.winner)
		loser = self.get_account_info(summary.loser)
		# Step 1
		if winner["stake"] < TRANSACTION_FEE or loser["stake"] < TRANSACTION_FEE:
			return False
		# Step 2		
		if (not winner["in_encounter_with"] or
			not loser["in_encounter_with"] or
			winner["in_encounter_with"] != summary.loser or
			loser["in_encounter_with"] != summary.winner
		):
			return False
		# Step 3
		if winner["encounter_begin_at"] > winner["current_ledger"]:
			return False
		# Step 4
		if winner["encounter_end_by"] < winner["current_ledger"]:
			return False
		return True

	def is_valid_coinstake_summary(self, css):
		# These transactions should be dropped
		# if they're not approved in the very next ledger
		return self.get_ledger_root()["ledger_number"] == 1 + css.for_voting_on_changes_to_ledger_number

	# Take a set of transactions and apply them to the ledger one by one.
	def apply_transactions(self, txs):
		coinstakes = set()
		# The transactions must be sorted first, so that all voters apply them in the same order
		txs_sorted = sorted(list(txs), key = lambda t: t.id)
		for tx in txs_sorted:
			tx_type = str(tx.__class__)
			logging.info("Applying "+tx_type+" transaction to the ledger...")
			if tx_type == "consensor.InitiationSummary":
				if self.is_valid_initiation_summary(tx):
					self.initiate_encounter(tx) # Modifies the ledger
			elif tx_type == "consensor.EncounterSummary":
				if self.is_valid_encounter_summary(tx):
					self.close_encounter(tx) # Modifies the ledger
			elif tx_type == "consensor.CoinstakeSummary":
				if self.is_valid_coinstake_summary(tx):
					coinstakes.add(tx)					
			else:
				# An unknown transaction type should never have made it this far, but just in case...
				logging.info("Could not apply: unknown transaction type")

		"""
		There's a small bug here: If a transaction is dropped at the last minute,
		because it's inconsistent with another transaction that got sorted before
		it in txs_sorted, then the voters will still earn a fee at the next round
		as if the fee for the dropped transaction had been paid.
		"""

		# Calculate transaction fees
		if len(coinstakes):
			denominator = 0
			total_fees = 0
			for cs in coinstakes:
				payee_stake = self.get_account_info(cs.payee)["stake"]
				denominator += payee_stake
				if total_fees is not 0:
					assert total_fees == cs.total_fees # They should all be the same
				total_fees = cs.total_fees
			# Determine reward by "House of Representatives" method, breaking ties alphabetically
			# (since the reward has to be an integer)
			reward_per_stake = float(total_fees)/denominator
			unallocated_reward = total_fees
	        rvs = list()
	        for cs in coinstakes:
	            reward = self.get_account_info(cs.payee)["stake"] * reward_per_stake
	            rv = {"payee": cs.payee, "short_id": cs.short_id()}
	            rv["reward"] = reward
	            rv["integer_reward"] = int(reward)
	            unallocated_reward -= int(reward)
	            rvs.append(rv)
	        rvs.sort(key=lambda x: x["payee"])
	        rvs.sort(key=lambda x: -x["reward"])
	        for rv in rvs:
	            if unallocated_reward:
	                rv["integer_reward"] += 1
	                unallocated_reward -= 1
	            else:
	                break
	        for rv in rvs:
	        	self.pay_coinstake(rv) # Modifies the ledger
		
		# Update the ledger root and ledger hash
		self.update_root_and_hash()

	# Write an InitiateEncounter transaction into the ledger
	def initiate_encounter(self, summary):
		challenger = self.get_account_info(summary.challenger)
		defender = self.get_account_info(summary.defender)
		
		c = self.conn.cursor()
		c.execute('''UPDATE ledger_main SET
			stake=?,
			in_encounter_with=?,
			encounter_begin_at=?,
			encounter_end_by=?
			WHERE account_id=?''', (
				challenger["stake"]-TRANSACTION_FEE,	# stake
				defender["account_id"],					# in_encounter_with
				challenger["current_ledger"],			# encounter_begin_at
				summary.encounter_end_by,				# encounter_end_by
				challenger["account_id"]
			)
		)
		c.execute('''UPDATE ledger_main SET
			stake=?,
			in_encounter_with=?,
			encounter_begin_at=?,
			encounter_end_by=?
			WHERE account_id=?''', (
				defender["stake"]-TRANSACTION_FEE,		# stake
				challenger["account_id"],				# in_encounter_with
				defender["current_ledger"],				# encounter_begin_at
				summary.encounter_end_by,				# encounter_end_by
				defender["account_id"]
			)
		)
		logging.info("Applied InitiateEncounter "+summary.short_id()+" to the ledger.")

	# Write a CloseEncounter transaction into the ledger
	def close_encounter(self, summary):
		winner = self.get_account_info(summary.winner)
		loser = self.get_account_info(summary.loser)

		if summary.was_tied:
			(new_winner_skill, new_loser_skill) = (winner["skill"], loser["skill"])
		else:
			(new_winner_skill, new_loser_skill) = skill_change(winner["skill"], loser["skill"])
		
		c = self.conn.cursor()
		c.execute('''UPDATE ledger_main SET
			skill=?,
			stake=?,
			in_encounter_with=NULL,
			encounter_begin_at=NULL,
			encounter_end_by=NULL,
			partial_chain_length=NULL
			WHERE account_id=?''',
			(new_winner_skill, winner["stake"]-TRANSACTION_FEE, winner["account_id"])
		)
		c.execute('''UPDATE ledger_main SET
			skill=?,
			stake=?,
			in_encounter_with=NULL,
			encounter_begin_at=NULL,
			encounter_end_by=NULL,
			partial_chain_length=NULL
			WHERE account_id=?''',
			(new_loser_skill, loser["stake"]-TRANSACTION_FEE, loser["account_id"])
		)
		self.conn.commit()
		logging.info("Applied CloseEncounter "+summary.short_id()+" to the ledger.")

	# Write a Coinstake transaction into the ledger
	def pay_coinstake(self, rv):
		# pay rv["integer_reward"] to rv["payee"]
		payee = self.get_account_info(rv["payee"])
		c = self.conn.cursor()
		c.execute('''UPDATE ledger_main SET
			stake=?
			WHERE account_id=?''',
			(payee["stake"]+rv["integer_reward"], payee["account_id"])
		)
		self.conn.commit()
		logging.info("Applied CoinStake "+rv["short_id"]+" to the ledger.")

	# Update the bookkeeping data that's used to keep track of each ledger.
	def update_root_and_hash(self):
		c = self.conn.cursor()
		hashes = ""
		for entry in c.execute("SELECT * FROM ledger_main ORDER BY account_id"):
			entry_hash = hashlib.sha256(str(entry)).hexdigest()
			hashes += entry_hash
		merkle_root = hashlib.sha256(hashes).hexdigest()
		# This is not actually a Merkle tree; but the ledger isn't so big that we need that.
		ledger_number = 1+self.get_ledger_root()["ledger_number"]
		previous_hash = self.get_ledger_hash()
		c.execute("UPDATE ledger_root SET merkle_root=?, ledger_number=?, previous_hash=?",
			(merkle_root, ledger_number, previous_hash))
		new_ledger_hash = hashlib.sha256(str(self.get_ledger_root())).hexdigest()
		logging.info("Updating ledger hash: "+new_ledger_hash[0:9]+"...")
		c.execute("UPDATE ledger_hash SET ledger_hash=?", (new_ledger_hash,))
		self.conn.commit()

	# Get an account's data from the ledger
	def get_account_info(self, account_id):
		c = self.conn.cursor()
		c.execute("SELECT * FROM ledger_main WHERE account_id = ?", (account_id,))
		r = c.fetchone()
		if r:
			c.execute("SELECT * FROM ledger_root")
			root = c.fetchone()
			r["current_ledger"] = root["ledger_number"]
			return r
		else:
			result = None
		#self.conn.close()
		return result

	def get_ledger_root(self):
		c = self.conn.cursor()
		c.execute("SELECT * FROM ledger_root")
		r = c.fetchone()
		return r

	def get_ledger_hash(self):
		c = self.conn.cursor()
		c.execute("SELECT * FROM ledger_hash")
		r = c.fetchone()
		result = r["ledger_hash"] #something
		#self.conn.close()
		return result


# Create a new database, if there isn't already one on disk
def initalize_database(conn):
	c = conn.cursor()

	# Create table
	c.execute('''CREATE TABLE ledger_main(
		account_id TEXT NOT NULL UNIQUE,
		stake INTEGER NOT NULL, 
		skill INTEGER NOT NULL, 
		in_encounter_with TEXT DEFAULT NULL, 
		encounter_begin_at INTEGER DEFAULT NULL,
		encounter_end_by INTEGER DEFAULT NULL,
		partial_chain_length INTEGER DEFAULT NULL
	)''')

	c.execute('''CREATE TABLE ledger_root(
		merkle_root TEXT NOT NULL,
		ledger_number INTEGER NOT NULL, 
		previous_hash TEXT NOT NULL
	)''')

	c.execute('''CREATE TABLE ledger_hash(
		ledger_hash TEXT NOT NULL
	)''')

	conn.commit()



import math
"""
The skill change formula:
	d = 1/( 1 + exp(W-L) )
	W' = W + d
	L' = L - d
"""
def skill_change(winner_skill, loser_skill):
	k = 1000
	w = float(winner_skill) / k
	l = float(loser_skill) / k
	d = 1 / (1 + math.exp(w-l))
	w_ = w + d
	l_ = l - d
	return (int(round(w_ * k)), int(round(l_ * k)))
