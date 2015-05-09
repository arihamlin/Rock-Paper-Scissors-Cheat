import sqlite3
GENESIS_ACCOUNT_ID = "ZDRlNjg0ZDgyOGEyYTY5ZjY4MDYxZjhiYzZiYzFjNjJmZjlj"

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


	def apply_transactions(self, txs):
		pass
		for tx in txs:
			pass #do stuff
		#update the ledger root and ledger hash
		#ledger_number = self.get_ledger_root()["ledger_number"]
		self.update_root_and_hash()
		#self.save()

	def update_root_and_hash(self):
		c = self.conn.cursor()
		hashes = list()
		for entry in c.execute("SELECT * FROM ledger_main ORDER BY account_id"):
			entry_hash = 123456 #something from entry
			hashes.append(entry_hash)
		merkle_root = merkle_root_from_leaves(hashes)
		ledger_number = 1+self.get_ledger_root()["ledger_number"]
		previous_hash = self.get_ledger_hash()

		ledger_hash = "deadbeef" #something

		c.execute("UPDATE ledger_root SET merkle_root=?, ledger_number=?, previous_hash=?",
			(merkle_root, ledger_number, previous_hash))
		c.execute("UPDATE ledger_hash SET ledger_hash=?", (ledger_hash,))
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
		result = {
			"merkle_root": "deadbeef", #something
			"ledger_number": 1, #something
			"previous_hash": "8badf00d" #something
		}
		#self.conn.close()
		return result

	def get_ledger_hash(self):
		c = self.conn.cursor()
		c.execute("SELECT * FROM ledger_hash")
		r = c.fetchone()
		result = "defaced1" #something
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


def is_power_of_two(num):
	return num != 0 and ((num & (num - 1)) == 0)


def merkle_root_from_leaves(leaves):
	while not is_power_of_two(len(leaves)):
		leaves.append(0)
	while len(leaves) > 1:
		next_level = list()
		for i in xrange(len(leaves) / 2):
			next_hash = 543321 #hash of leaves[2i] concat leaves[2i+1]
			next_level.append(next_hash)
		leaves = next_level
	return leaves[0]


import math

"""
d = 1/( 1 + exp(W-L) )
W' = W + d
L' = L - d
"""
def skill_change(winner, loser):
	k = 1000
	w = float(winner) / k
	l = float(loser) / k
	d = 1 / (1 + math.exp(w-l))
	w_ = w + d
	l_ = l - d
	return (int(round(w_ * k)), int(round(l_ * k)))
