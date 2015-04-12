"""
The ledger contains entries with the following fields:
account_id: String, the hash of the public key
stake: Integer, how much money they have
skill: Integer, their skill (ELO) rating
encounter_with: String, who they're in an encounter with (optional)
encounter_started: Integer, when that encounter started (optional)

The ledger root contains:
merkle_root: String, the hash of all the ledger entries
ledger_number: Integer, the incrementing count of the ledgers
previous_hash: String, the hash of the previous ledger

The ledger hash is the hash of the ledger root. Signatures are computed off of this.
"""
class Ledger():

	def apply_transactions(self, txs):
		pass
		for tx in txs:
			pass #do stuff
		pass #update the ledger root and ledger hash

	def get_account_info(self, account_id):
		pass

	def get_ledger_root(self):
		pass

	def get_ledger_hash(self):

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
