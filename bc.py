import hashlib
import json
from time import time
from urllib.parse import urlparse
from uuid import uuid4

import requests
from flask import Flask, jsonify, request

class Blockchain():
    def __init__(self):
        self.chain = []
        self.current_trxs = []
        self.nodes = set()
        self.new_block(previous_hash=1, proof=100)

    def new_block(self, proof, previous_hash=None):
        block = {
            'index' : len(self.chain) + 1,
            'timestamp' : time(),
            'trxs' : self.current_trxs,
            'proof' : proof,
            'previous_hash' : previous_hash or self.hash(self.chain[-1])
        }
        self.current_trxs = []

        self.chain.append(block)

        return block


    def new_trx(self, sender , recipient, amount):
        ''' define new transaction in mem pool '''
        self.current_trxs.append({'sender': sender,'recipient': recipient,'amount': amount})
    
        return self.last_block['index'] + 1


    def register_node(self, address):
        parsed_url = urlparse(address)
        if parsed_url.netloc:
            self.nodes.add(parsed_url.netloc)
        elif parsed_url.path:
            # Accepts an URL without scheme like '192.168.0.5:5000'.
            self.nodes.add(parsed_url.path)
        else:
            raise ValueError('Invalid URL')

    def valid_chain(self,chain):
        ''' check chain is true '''
        last_block=chain[0]
        current_index = 1
        while current_index < len(chain):
            block = chain[current_index]
            if block['previous_hash'] != self.hash(last_block):
                return False
            if not self.valid_proof(last_block['proof'], block['proof']):
                return False
            last_block = block
            current_index += 1 

        return True

    def resolve_conflicts(self):
        ''' check all node and return best node '''
        neighbours = self.nodes
        new_chain = None

        max_length = len(self.chain)
        for node in neighbours:
            response = requests.get(f'http://{node}/chain')
            if response.status_code == 200:
                length = response.json()['length']
                chain = response.json()['chain']
                if length > max_length and self.valid_chain(chain):
                    max_length = length
                    new_chain = chain


        if new_chain:
            self.chain = new_chain
            return True

        return False


    @staticmethod
    def hash(block):
        ''' hash a block '''
        block_string = json.dumps(block, sort_keys= True).encode()
        return hashlib.sha256(block_string).hexdigest()
    
    @property
    def last_block(self):
        ''' return last block '''
        return self.chain[-1]
 
    @staticmethod
    def valid_proof(last_proof, proof):
        ''' check if this proof is valid or not '''
        this_proof = f"{proof}{last_proof}".encode()
        this_proof_hash = hashlib.sha256(this_proof).hexdigest()
        return this_proof_hash[:4] == '0000'

    def proof_of_work(self, last_proof):
        ''' shows that the work is done '''
        proof = 0
        while self.valid_proof(last_proof, proof) is False:
            proof += 1

        return proof


app = Flask(__name__)

node_id = str(uuid4())

blockchain = Blockchain()

@app.route('/mine', methods=['GET'])
def mine():
    ''' mine one block and add to chain '''
    last_block = blockchain.last_block
    last_proof = last_block['proof']
    proof = blockchain.proof_of_work(last_proof)

    blockchain.new_trx(sender="0", recipient=node_id, amount=50)
    
    previous_hash = blockchain.hash(last_block)
    block = blockchain.new_block(proof, previous_hash)

    res = {
        'message': 'new block created',
        'index': block['index'],
        'trxs' : block['trxs'],
        'proof' : block['proof'],
        'previous_hash' : block['previous_hash']
    }
    return jsonify(res), 200


@app.route('/trxs/new', methods=['POST'])
def new_trx():
    ''' will add new trxs '''
    values = request.get_json()
    this_block = blockchain.new_trx(values['sender'], values['recipient'], values['amount'])
    res = {'message': f"will be added to block {this_block}"}
    return jsonify(res), 201

@app.route('/chain')
def full_chain():
    res = {
        'chain' : blockchain.chain,
        'length' : len(blockchain.chain)
    }
    return jsonify(res), 200


@app.route('/nodes/register', methods=['POST'])
def register_node():
    values = request.get_json()

    nodes = values.get('nodes')
    for node in nodes:
        blockchain.register_node(node)

    res = {
        'message' : 'nodes added',
        'total_nodes' : list(blockchain.nodes)
    }
    return jsonify(res), 201
    
@app.route('/nodes/resolve', methods=['GET'])
def consensus():
    replaced = blockchain.resolve_conflicts()

    if replaced:
        response = {
            'message': 'Our chain was replaced',
            'new_chain': blockchain.chain
        }
    else:
        response = {
            'message': 'Our chain is authoritative',
            'chain': blockchain.chain
        }

    return jsonify(response), 200

if __name__ == '__main__':
    from argparse import ArgumentParser

    parser = ArgumentParser()
    parser.add_argument('-p', '--port', default=5000, type=int, help='port to listen on')
    args = parser.parse_args()
    port = args.port

    app.run(host='0.0.0.0', port=port)