import sys
# sys.path.insert(0, 'build/shared_model/bindings')
import iroha

import block_pb2
import endpoint_pb2
import endpoint_pb2_grpc
import queries_pb2
import grpc
import time

from google.protobuf.json_format import MessageToJson
from google.protobuf import json_format

import json

tx_builder = iroha.ModelTransactionBuilder()
query_builder = iroha.ModelQueryBuilder()
crypto = iroha.ModelCrypto()
proto_tx_helper = iroha.ModelProtoTransaction()
proto_query_helper = iroha.ModelProtoQuery()


# admin_priv = open("../admin@test.priv", "r").read()
# admin_pub = open("../admin@test.pub", "r").read()
# key_pair = crypto.convertFromExisting(admin_pub, admin_priv)


def get_current_time():
    return int(round(time.time() * 1000)) - 10 ** 5


def load_keypair(path):
    """
    Load keypair from path
    :param path: file path
    :return: Key Pair
    """
    priv_key = open(path + ".priv", "r").read()
    pub_key = open(path + ".pub", "r").read()
    ans = {"pub_key": pub_key, "priv_key": priv_key, "key_pair": crypto.convertFromExisting(pub_key, priv_key)}
    return ans


def get_tx_status(tx, address='127.0.0.1:50051'):
    """
    Get status of the transaction
    :param tx: iroha transaction
    :param address: ip address and iroha port
    :return: status of tx transaction
    """
    # Create status request

    print("Hash of the transaction: ", tx.hash().hex())
    tx_hash = tx.hash().blob()

    if sys.version_info[0] == 2:
        tx_hash = ''.join(map(chr, tx_hash))
    else:
        tx_hash = bytes(tx_hash)

    request = endpoint_pb2.TxStatusRequest()
    request.tx_hash = tx_hash
    #
    channel = grpc.insecure_channel(address)
    stub = endpoint_pb2_grpc.CommandServiceStub(channel)

    response = stub.Status(request)
    status = endpoint_pb2.TxStatus.Name(response.tx_status)
    return status


def print_status_streaming(tx_hash, address='127.0.0.1:50051'):
    # Create status request

    # print("Hash of the transaction: ", tx.hash().hex())
    tx_hash = tx_hash.blob()

    # Check python version
    if sys.version_info[0] == 2:
        tx_hash = ''.join(map(chr, tx_hash))
    else:
        tx_hash = bytes(tx_hash)

    # Create request
    request = endpoint_pb2.TxStatusRequest()
    request.tx_hash = tx_hash

    # Create connection to Iroha
    channel = grpc.insecure_channel(address)
    stub = endpoint_pb2_grpc.CommandServiceStub(channel)

    # Send request
    response = stub.StatusStream(request)

    for status in response:
        print("Status of transaction:")
        print(status)


def form_tx(tx, key_pair):
    tx_blob = proto_tx_helper.signAndAddSignature(tx, key_pair).blob()
    proto_tx = block_pb2.Transaction()

    if sys.version_info[0] == 2:
        tmp = ''.join(map(chr, tx_blob))
    else:
        tmp = bytes(tx_blob)

    proto_tx.ParseFromString(tmp)
    return proto_tx

def proto_to_JSON(proto_tx):
    return MessageToJson(proto_tx)


def send_tx(tx, key_pair, address='127.0.0.1:50051'):
    tx_blob = proto_tx_helper.signAndAddSignature(tx, key_pair).blob()
    proto_tx = block_pb2.Transaction()

    if sys.version_info[0] == 2:
        tmp = ''.join(map(chr, tx_blob))
    else:
        tmp = bytes(tx_blob)

    proto_tx.ParseFromString(tmp)

    channel = grpc.insecure_channel(address)
    stub = endpoint_pb2_grpc.CommandServiceStub(channel)

    stub.Torii(proto_tx)


def send_formed_tx(proto_tx, address='127.0.0.1:50051'):

    # l_r["Payload"] = l_r["payload"]
    # del l_r["payload"]
    # proto_tx = json_format.Parse(l_r, endpoint_pb2.Transaction, ignore_unknown_fields=False)
    # proto_tx = block_pb2.Transaction()
    # proto_tx.ParseFromJson(l_r)

    channel = grpc.insecure_channel(address)
    stub = endpoint_pb2_grpc.CommandServiceStub(channel)

    stub.Torii(proto_tx)


def send_query(query, key_pair, address='127.0.0.1:50051'):
    """
    Send query to iroha address
    :param query: to send
    :param key_pair: for signatures
    :param address: iroha address
    :return: query response
    """
    query_blob = proto_query_helper.signAndAddSignature(query, key_pair).blob()

    proto_query = queries_pb2.Query()

    if sys.version_info[0] == 2:
        tmp = ''.join(map(chr, query_blob))
    else:
        tmp = bytes(query_blob)

    proto_query.ParseFromString(tmp)

    channel = grpc.insecure_channel(address)
    query_stub = endpoint_pb2_grpc.QueryServiceStub(channel)
    query_response = query_stub.Find(proto_query)

    return MessageToJson(query_response)


def parseAccountDetails(proto_message):
    return json.loads(json.loads(proto_message)["accountDetailResponse"]["detail"])
