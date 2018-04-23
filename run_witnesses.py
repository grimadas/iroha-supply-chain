from witness import Witness, Actor, fetch_message
from time import sleep
import json

# Create static witnesses

wits = {}
for i in range(1, 9):
    wits[i] = Witness(i, is_honest=True, num_rounds=5, message_delay=100)

# Create other actors
client = Actor("client", True)
producer = Actor("producer", True)
transport = Actor("transport", True)
store = Actor("store", True)

admin = Actor("admin", True)

# Admin is creating assets, transferring to client
print("Bank creates and send to client coins")
coin_tx = admin \
    .prepare_tx() \
    .addAssetQuantity(admin.name, "coin#test", "10.00") \
    .transferAsset(admin.name, client.name, "coin#test", "", "5.00") \
    .build()
admin.send_tx(coin_tx)

# Producer is creating goods
print("Producer creates goods")
goods_tx = producer \
    .prepare_tx() \
    .addAssetQuantity(producer.name, "goods#test", "3") \
    .build()
producer.send_tx(goods_tx)
sleep(1)
# Producer and client are communicating off-chain to communicating on terms of the exchange

# 6. When transport arrives to the client, client creates are ending multisignature contract:
# - transfer from transport to client - goods, transfer coins to producer
# The transfer is considered finished only if all three actors sign the transaction

# Client - Transport - Producer exchange
# Starting contract
# 0. Transport is granting permissions to add signatories, quorum to the account
print("Transport grants permissions")
init_tx = transport \
    .prepare_tx() \
    .grantPermission(client.name, "can_set_my_quorum") \
    .grantPermission(transport.name, "can_set_my_quorum") \
    .grantPermission(client.name, "can_add_my_signatory") \
    .grantPermission(transport.name, "can_add_my_signatory") \
    .build()
# transport.send_tx(init_tx)
# sleep(1)
# 1. Client add signatory and changes the quorum of transaction account
# /and sending number of coin that cover also transport fees
# / client adds end location
print("Client add signatory and add data")
client_tx = client.prepare_tx() \
    .transferAsset(client.name, transport.name, "coin#test", "", "4.20") \
    .setAccountDetail(transport.name, "lp_time_end", str(client.now)) \
    .setAccountDetail(transport.name, "lp_location_end", str(client.location)) \
    .build()
client.send_tx(client_tx)

# 2. Producer is adding signatory and increases quorum / Producer is sending goods to transport
# Producer must check that client has put signatory to account
# / Producer add starting location and starting time
print("Producer adds signatory and data")
producer_tx = producer.prepare_tx() \
    .transferAsset(producer.name, transport.name, "goods#test", "", "1") \
    .setAccountDetail(transport.name, "lp_time_start", str(producer.now)) \
    .setAccountDetail(transport.name, "lp_location_start", str(producer.location)) \
    .build()
producer.send_tx(producer_tx)
sleep(1)
# 3. Transport start moving from "start" location to "end"
end_loc = json.loads(client.location)
transport.location = producer.location
cur_loc = json.loads(transport.location)
planned_trajectory = [[2, 2], [3, 2], [4, 2], [5, 2], [5, 3], [5, 4], [6, 4], [7, 4], [7, 3], [7, 2], [8, 2]]

# Transport moves
# Transport - Witness proximity test
step = 0
while cur_loc != end_loc:
    # Move one step
    sleep(0.5)
    cur_loc = planned_trajectory[step]
    print("Transport is moving to ", cur_loc)
    # Get witness in near proximity (can be replaced with query to iroha)
    near_wits = []
    for wit in wits.values():
        if cur_loc == json.loads(wit.actor.location):
            near_wits.append(wit)
    for wit in near_wits:
        # There is witness nearby
        ping_message = "ping"
        round_num = 0
        while True:
            print("Proximity_test Round with witness ", round_num, wit)
            ping = transport.proximity_tx(wit.actor.name, ping_message)
            pong = wit.location_test(transport.name, ping)
            if transport.proximity_test(wit.actor.name, pong):
                break
            else:
                ping_message = fetch_message(pong)
                round_num += 1
                if round_num > 10:
                    # witness is not confirming
                    print("Witness "+str(wit.actor.name) + " is not confirming proximity")
                    break
    step += 1
print("Transport is near client, making ending contract")

# Ending smart contract
end_contract = transport \
    .prepare_tx() \
    .transferAsset(transport.name, client.name, "goods#test", "", "1") \
    .transferAsset(transport.name, producer.name, "coin#test", "", "4.00")\
    .setAccountDetail(transport.name, "lp_time_end", str(transport.now))\
    .build()
transport.send_tx(end_contract)
sleep(1)
# Get full trajectory
print("Fetch trajectory of transport -----")
q = transport.prepare_query()\
    .getAccountDetail(transport.name)\
    .build()
print(transport.send_query(q))

#  Client at moment T queries all location points and builds a trajectory
# Admin queries information about the transport locations and verifies the validity
