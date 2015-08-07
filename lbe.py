# LBE - Lite Block Explorer
# Author: Ondrej Sika <ondrej@ondrejsika.com>
# License: MIT <http://ondrejsika.com/license/mit.txt>

import argparse

from flask import Flask, render_template
from jsonrpc_requests import Server, TransportError, ProtocolError


parser = argparse.ArgumentParser('LBE - Light Blockchain Explorer')
parser.add_argument('PORT', type=int)
parser.add_argument('XCOIND_HOST', type=str)
parser.add_argument('XCOIND_PORT', type=int)
parser.add_argument('XCOIND_USER', type=str)
parser.add_argument('XCOIND_PASSWORD', type=str)

args = parser.parse_args()


class LocalCache(object):
    _storage = None

    def __init__(self):
        self._storage = {}

    def set(self, key, val):
        self._storage[key] = val

    def get(self, key):
        return self._storage.get(key)


class Xcoind(object):
    _rpc = None
    _cache = None

    def __init__(self, host, port, user, password, cache=None):
        self._rpc_server = Server('http://%s:%s' % (host, port), auth=(user, password))
        self._cache = cache if cache else LocalCache()

    def rpc(self, method, *params):
        cachekey = 'rpc__%s_%s' % (method, str(params))
        resp = self._cache.get(cachekey)
        if resp:
            return resp
        resp = self._rpc_server.send_request(method, False, params)
        self._cache.set(cachekey, resp)
        return resp

    def getbestblockhash(self):
        return self.rpc('getbestblockhash')

    def getblock(self, hash):
        return self.rpc('getblock', hash, True)

    def getlastnblocks(self, limit):
        lastblockhash = self.getbestblockhash()
        cachekey = 'getlastnblocks__%s__%s' % (lastblockhash, limit)

        blocks = self._cache.get(cachekey)
        if blocks:
            return blocks

        last = self.getblock(lastblockhash)
        blocks = [last]
        for i in range(limit):
            if not 'previousblockhash' in last:
                break
            last = self.getblock(last['previousblockhash'])
            blocks.append(last)

        self._cache.set(cachekey, blocks)
        return blocks

    def gettx(self, tx_hash):
        raw = self.rpc('getrawtransaction', tx_hash)
        return self.rpc('decoderawtransaction', raw)

    def gettxs(self, tx_hashes):
        cachekey = 'gettxs__%s' % str(tx_hashes)
        txs = self._cache.get(cachekey)
        if txs:
            return txs

        txs = []
        for tx_hash in tx_hashes:
            tx = self.gettx(tx_hash)
            txs.append(tx)

        self._cache.set(cachekey, txs)
        return txs

    def getsimpletx(self, txid):
        tx = self.gettx(txid)
        is_coinbase = True if 'coinbase' in tx['vin'][0] else False
        vins = []
        if not is_coinbase:
            for vin in tx['vin']:
                in_tx = self.gettx(vin['txid'])
                for in_vout in in_tx['vout']:
                    if vin['vout'] == in_vout['n']:
                        vins.append({
                            'address': in_vout['scriptPubKey']['addresses'][0] if 'addresses' in in_vout['scriptPubKey'] else None,
                            'value': in_vout['value'],
                        })

        vouts = []
        for vout in tx['vout']:
            vouts.append({
                'address': vout['scriptPubKey']['addresses'][0] if 'addresses' in vout['scriptPubKey'] else None,
                'value': vout['value'],
            })
        return {
            'txid': txid,
            'is_coinbase': is_coinbase,
            'vin': vins,
            'vout': vouts,
            'tx': tx,
        }

xcoind = Xcoind(args.XCOIND_HOST, args.XCOIND_PORT, args.XCOIND_USER, args.XCOIND_PASSWORD)

app = Flask(__name__)


@app.route('/')
def index():
    try:
        blocks = xcoind.getlastnblocks(100)
    except (TransportError, ProtocolError):
        return render_template('error_xcoind.html')
    return render_template('index.html', blocks=blocks)


@app.route('/block/<hash>')
def block(hash):
    try:
        block = xcoind.getblock(hash)
    except (TransportError, ProtocolError):
        return render_template('error_xcoind.html')

    return render_template('block.html', block=block)

@app.route('/tx/<hash>')
def tx(hash):
    try:
        tx = xcoind.getsimpletx(hash)
    except (TransportError, ProtocolError):
        return render_template('error_xcoind.html')

    return render_template('tx.html', tx=tx)

if __name__ == '__main__':
    app.debug = True
    app.run()

