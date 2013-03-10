from dateutil import parser
from jsonrpc import proxy
import pprint
from time import sleep

def deserializeStat(data):
    """convert dates back to python objects"""
    if 'timestamp' in data:
        data['timestamp'] = parser.parse(data['timestamp'])
        
    if 'transactions' in data:
        txs = data['transactions']
        for tx in txs:
            tx['date'] = parser.parse(tx['date'])
        
    if 'dividends' in data:
        divs = data['dividends']
        for div in divs:
            div['date'] = parser.parse(div['date'])
            
    return data    
    

def readonlyExample(mpexproxy,pp):
    #just a STAT call
    statres = mpexproxy.statjson()
    pp.pprint(deserializeStat(statres))

def placeCancelExample(mpexproxy,pp):
    #new order to buy 1 S.MPOE at 0.00023456 BTC
    res = mpexproxy.neworder('B','S.MPOE',1,23456)
    pp.pprint(res)
    sleep(5)
    statres = mpexproxy.stat()
    #cancels first order in stat list (it might be different order than we just placed!)
    res = mpexproxy.cancel(statres['orders'].keys()[0])
    pp.pprint(res)

if __name__ == '__main__':
    mpexproxy = proxy.JSONRPCProxy('http://localhost:8077', '/jsonrpc')
    pp = pprint.PrettyPrinter(indent=2)
    readonlyExample(mpexproxy,pp)
    #placeCancelExample(mpexproxy,pp)

