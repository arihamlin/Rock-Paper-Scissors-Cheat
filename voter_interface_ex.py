import tornado.httpclient
import json
from common.base import QueryState, SignedStructure
from common.helpers import get_account_from_seed

"""
Start a relay (relay listens on port 10000 and HTTP server on 10001):
$ python voters/relay.py 10000 10001

Start a voter:
$ python voters/voter.py 127.0.0.1 10000 voter_account_id
"""


account = get_account_from_seed(5124)

"""
Build a signed structure for request types: QueryState, InitiateEncounter,
and send it in HTTP POST body to relay.
"""
req = SignedStructure(
    QueryState(account_id=account.account_id))
req.sign(account)

client = tornado.httpclient.HTTPClient()
r = client.fetch("http://127.0.0.1:10001/?nnodes=1&nresponses=1",
    method="POST", body=req.serialize())


"""
Responses from voters are returned in a list in 'responses' field of JSON object returned.
"""
results = json.loads(r.body)["responses"]
for r in results:
    deserialized = SignedStructure.deserialize(r)
    print deserialized
