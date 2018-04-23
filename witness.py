import iroha_bridge
import json

from random import randint


def fetch_message(message):
    return json.loads(message)["payload"]["commands"][0]["transferAsset"][
        "description"]


class Actor:

    def sign_tx(self, tx):
        return iroha_bridge.form_tx(tx, self.key_pair)

    def send_tx(self, tx):
        iroha_bridge.send_tx(tx, self.key_pair, self.peer_address)
        iroha_bridge.print_status_streaming(tx.hash(), self.peer_address)

    def send_query(self, query):
        return iroha_bridge.send_query(query, self.key_pair, self.peer_address)

    def update_clock(self):
        self.now = iroha_bridge.get_current_time()

    def prepare_tx(self):
        self.update_clock()
        return iroha_bridge.tx_builder \
            .creatorAccountId(self.name) \
            .createdTime(self.now)

    def prepare_query(self):
        self.query_counter += 1
        self.update_clock()
        return iroha_bridge.query_builder \
            .creatorAccountId(self.name) \
            .createdTime(self.now) \
            .queryCounter(self.query_counter)

    def __init__(self, name, is_honest, peer_address='127.0.0.1:50051'):
        self.name = name + "@test"
        self.is_honest = is_honest
        val = iroha_bridge.load_keypair("keys/" + self.name)
        self.key_pair = val["key_pair"]
        self.pub_key = val["pub_key"]
        self.query_counter = 0
        self.now = iroha_bridge.get_current_time()
        self.peer_address = peer_address
        self.location = self.get_genesis_location(self.name)

    def proximity_tx(self, dest, message):
        tx = self.prepare_tx() \
            .transferAsset(self.name, dest, "goods#test", message, "1") \
            .build()
        return iroha_bridge.proto_to_JSON(iroha_bridge.form_tx(tx, self.key_pair))

    def validateSignature(self, acc_name, message):
        # Check validity of signature and account
        query = self.prepare_query() \
            .getSignatories(acc_name) \
            .build()
        response = iroha_bridge.send_query(query, self.key_pair, self.peer_address)
        acc_keys = json.loads(response)['signatoriesResponse']['keys']
        message_key = json.loads(message)["signature"][0]["pubkey"]
        #  Verify signature
        return message_key in acc_keys

    def validateTime(self, message_time):
        delta = 100  # clock imprecision
        max_delay = 5 * 1000  # max allowed delay
        self.update_clock()
        return self.now - max_delay < message_time < self.now + delta

    def get_genesis_location(self, account_id):
        # Get location info from Iroha node
        query = self.prepare_query() \
            .getAccountDetail(account_id) \
            .build()
        response = iroha_bridge.send_query(query, self.key_pair, self.peer_address)
        # pprint(response)
        val = iroha_bridge.parseAccountDetails(response)
        if 'genesis' not in val.keys() or 'location' not in val['genesis']:
            return [0, 0]
        return val['genesis']['location']

    def proximity_test(self, acc_name, message):
        if type(message) == dict:
            # Message in proto Format
            json_data = iroha_bridge.proto_to_JSON(message["message"])
            json_data_parsed = json.loads(json_data)
        else:
            # Message in json format
            json_data_parsed = json.loads(message)
            json_data = message
        message_time = int(json_data_parsed["payload"]["txCounter"])
        if self.validateTime(message_time) and self.validateSignature(acc_name, json_data):
            if "setAccountDetail" in json_data_parsed["payload"]["commands"][0].keys():
                # Confirmation message received, forward to iroha
                print("Confirmation message received")

                iroha_bridge.send_formed_tx(message["message"])
                iroha_bridge.print_status_streaming(message["hash"])
                return True
            else:
                return False


class Witness:
    def confirming_tx(self, acc_name):
        tx = self.actor.prepare_tx() \
            .setAccountDetail(acc_name, "lp_time_" + str(self.proximity[acc_name]["num"]), str(self.actor.now)) \
            .setAccountDetail(acc_name, "lp_location_" + str(self.proximity[acc_name]["num"]), str(self.actor.location)) \
            .build()
        return {"message": iroha_bridge.form_tx(tx, self.actor.key_pair), "hash": tx.hash()}

    def __init__(self, number, is_honest, num_rounds, message_delay, peer_address='127.0.0.1:50051'):
        self.actor = Actor("wit" + str(number), is_honest, peer_address)
        self.rounds = num_rounds
        self.delay = message_delay
        self.proximity = {}

    def location_test(self, acc_name, message):
        # Check validity of signature and account, and message time
        message_time = int(json.loads(message)["payload"]["txCounter"])
        if self.actor.validateSignature(acc_name, message) and self.actor.validateTime(message_time):
            if acc_name not in self.proximity.keys():
                self.proximity[acc_name] = {"num": 1, "times": 0, "last": 0, "last_secret": "ping"}
            if self.proximity[acc_name]["times"] < self.rounds:
                last = self.proximity[acc_name]["last"]
                self.actor.update_clock()
                last_secret = self.proximity[acc_name]["last_secret"]
                # generate new secret
                pong = str(randint(0, 100))
                if (last != 0 and message_time - last > self.delay) or \
                        fetch_message(message) != last_secret:
                    # Not valid response received
                    if self.proximity[acc_name]["times"] != 0:
                        self.proximity[acc_name]["times"] -= 1
                else:
                    self.proximity[acc_name]["times"] += 1
                self.proximity[acc_name]["last"] = self.actor.now
                self.proximity[acc_name]["last_secret"] = pong
                tx = self.actor.proximity_tx(acc_name, pong)
                return tx
            else:
                self.proximity[acc_name]["num"] += 1
                self.proximity[acc_name]["times"] = 0
                self.proximity[acc_name]["last"] = 0
                self.proximity[acc_name]["last_secret"] = "ping"
                return self.confirming_tx(acc_name)
