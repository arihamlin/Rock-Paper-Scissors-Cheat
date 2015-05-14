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

	# Write to the database
	#def save(self):
	#	pass

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
		#self.conn.close()
		self.update_root_and_hash()

	# Is a given InitiateEncounter summary valid, with respect to this ledger?
	def is_valid_initiation_summary(self, summary):
		# If they can afford the transaction fees, they're not already in encounters, and it's not too early or late.
		challenger = self.get_account_info(summary.challenger)
		defender = self.get_account_info(summary.defender)



		if challenger["stake"] < TRANSACTION_FEE or defender["stake"] < TRANSACTION_FEE:
			return False

		if challenger["in_encounter_with"] or defender["in_encounter_with"]:
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
		# commented out because we haven't set these values yet
		
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

	def apply_transactions(self, txs):
		for tx in txs:
			tx_type = str(tx.__class__)
			logging.info("Applying "+tx_type+" transaction to the ledger...")
			if tx_type == "consensor.InitiationSummary":
				if self.is_valid_initiation_summary(tx):
					self.initiate_encounter(tx) # Modifies the ledger
			elif tx_type == "consensor.EncounterSummary":
				if self.is_valid_encounter_summary(tx):
					self.close_encounter(tx) # Modifies the ledger
			elif tx_type == "consensor.CoinstakeSummary":
				pass
				#figure out how much each is owed
			else:
				logging.info("Could not apply: unknown transaction type")

		#update the ledger root and ledger hash
		#ledger_number = self.get_ledger_root()["ledger_number"]
		self.update_root_and_hash()
		#self.save()


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
				challenger["current_ledger"],				# encounter_begin_at
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



	def update_root_and_hash(self):
		c = self.conn.cursor()
		hashes = ""
		for entry in c.execute("SELECT * FROM ledger_main ORDER BY account_id"):
			entry_hash = hashlib.sha256(str(entry)).hexdigest() #something from entry
			hashes += entry_hash
		merkle_root = hashlib.sha256(hashes).hexdigest()
		# This is not actually a Merkle tree; but the ledger isn't so big that we need that.
		ledger_number = 1+self.get_ledger_root()["ledger_number"]
		previous_hash = self.get_ledger_hash()

		

		c.execute("UPDATE ledger_root SET merkle_root=?, ledger_number=?, previous_hash=?",
			(merkle_root, ledger_number, previous_hash))

		new_ledger_hash = hashlib.sha256(str(self.get_ledger_root())).hexdigest()
		logging.info("Updating ledger hash: "+new_ledger_hash)
		c.execute("UPDATE ledger_hash SET ledger_hash=?", (new_ledger_hash,))
		self.conn.commit()

		#self.conn.close()


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
	#conn.close()



import math

"""
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
