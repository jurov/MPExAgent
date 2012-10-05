# -*- coding: utf-8 -*-
import logging

#if __name__ == '__main__':
#    logging.basicConfig(filename='mpexagent.log',level=logging.DEBUG,format='%(asctime)s [%(name)s]:%(levelname)s:%(message)s')

log = logging.getLogger(__name__)
from pyparsing import *
from decimal import *
import datetime, sys
from dateutil import parser
import pdb
import pprint
# define some common fields such as <qty>, <value> or <MPSIC>
# for btcInt: we have ` as thousands separator: 12`345, so we just remove the '`'
#    this of course will accept (technically incorrect) values such as 1`00`345
btcInt  = Word(nums + '`').setParseAction(lambda s,l,t: [ t[0].replace('`', '') ]);
# NOTE: btcAmmount accepts values such as 123`456.674832, do we have the ` in ammounts
btcAmmount = Or(Combine(btcInt + '.' + Word(nums)) ^ btcInt)
btcName = Word(alphas + ".,-'()"); # NOTE: this is not (yet) used in the scrip
mpsic = Word(alphas + '.' + nums)

pp = pprint.PrettyPrinter(indent=2)

# generates a parsing from a list of fields
def getParser(fields):
    parser = ParserElement()
    for f in fields:
        parser += SkipTo(f) + f
    return parser

# since we are dealing with just a simple string,
# the return value is a list with only 1 item
# therefore, it can be used as a standalone field
# in more complex parsings
def getTradeFields():
    return [btcInt + mpsic + 'shares sold for' + btcAmmount + 'BTC each, for a total value of' + btcAmmount + 'BTC']


def getOrderFields():
    return [(Literal('BUY') ^ 'SELL') + btcInt + mpsic + '@' + btcAmmount + 'BTC each has been received and will be processed']


# generate parser fields for 'funding' messages
def getFundFields():
    addr = 'exchange address (' + Word(alphanums)("address") + ')'
    amnt = btcAmmount("ammount") + 'BTC'
    fields = [addr, amnt]
    return fields;

# generate parser fields for 'exercise' messages
def getExerciseFields():
    order = 'order to exercise' + btcInt("amount") + mpsic("mpsic") + 'contracts'
    total = 'will net you' + btcAmmount("total") + 'BTC'
    fields = [order, total]
    return fields;

# used to report that something has gone wrong.
# this, combined with checkEndToken allow to check if something
# went wrong in one of the fields, but not abort the whole parse action
def reportParseError(s, loc, expr, err):
    print >> sys.stderr, err

# we use this function to mark the end of groups of fields
# if Literal(string) fails, it means there was a problem
# parsing one of the fields.
def checkEndToken(string):
    return Optional(Literal(string).setFailAction(reportParseError))

def getStatFields():
    timestamp = '(' + Word(nums + '.') + Word(nums)("unixTimeStamp") + ')'

    # Issued today, Thursday the 19th of April 2012 at 12:06:00 PM (0.15819500 1334837160)
    datetime = 'Issued today,' + SkipTo('(') + timestamp

    # <MPSIC> x <qty>
    mpexField = Group(mpsic("mpsic") + 'x' + btcAmmount("qty"))
    
    # NOTE: don't know if the correct name is 'holdings'
    # NOTE: also, I presume there chould be ZeroOrMore(mpexFields) ?
    
    holdings = 'the following with MPEx :' + ZeroOrMore(mpexField)("current_holdings") +\
    checkEndToken('To which add orders')
    
    # <B/S> <qty> @ <price>BTC (order #<orderid>)
    orderValues = Word(alphas, max=1, exact=1) + btcInt + '@' + btcAmmount + 'BTC' + '(order #' + Word(nums) + ')'
    # <stock name> : <B/S> <qty> @ <price>BTC (order #<orderid>)
    orderField = Group(mpsic("stock") + ':' + orderValues("values"))
    orders = 'in advance :' + ZeroOrMore(orderField)("orders") +\
    checkEndToken('To which add sums')
    
    # <sum> BTC for <qty> <MPSIC> contracts.
    optionContractField = Group(btcAmmount("ammount") + 'BTC for' + btcAmmount("nrContracts") + mpsic("mpsic") + 'contracts' + Optional('.'))
    optionContracts = 'contracts :' + ZeroOrMore(optionContractField)("option_contracts") +\
    checkEndToken('Your transactions')

    # Thu, 19 Apr 12 12:03:48 +0000
    transactionDate = Group(Word(alphas) + "," + Word(nums) + Word(alphas) + Word(nums) + Word(nums) + ':' + Word(nums) + ':' + Word(nums) + (Literal('+')^'-') + Word(nums))

    # NOTE: check out the  pyparsing.Suppress('something') class
    # On <date> <MPSIC> - <qty> bought @<price> BTC, total cost <value>BTC
    # On <date> <MPSIC> - <qty> sold @<price>BTC, total yield <value>BTC

    transactionField = Group("On" + transactionDate + mpsic + '-' + btcInt + (Literal('bought') ^ 'sold') +\
     Suppress('@') + btcAmmount + (Literal('BTC, total cost') ^ 'BTC, total yield') + btcAmmount + 'BTC')
    transactions = 'last STAT :' + ZeroOrMore(transactionField)("transactions") +\
    checkEndToken('You have also been paid') 
    #dividends
    #You have also been paid dividends, as follows :
    #    On <date> from <MPSIC> the sum of <value> BTC
    dividendField = Group("On" + transactionDate + "from" + mpsic + "the sum of" + btcAmmount + 'BTC')
    dividends = 'dividends, as follows :' + ZeroOrMore(dividendField)("dividends") +\
    checkEndToken('The Great Seal')

    fields = [datetime, holdings, orders, optionContracts, transactions, dividends]
    return fields
# determines if the file matches against the keywords or not
def matchFileAgainstKeywords(fname, keywords, debug = False):
    parser = ParserElement()
    for kw in keywords:
        parser += SkipTo(kw)

    try:
        parser.parseFile(fname)
        return True
    except Exception as e:
        if (debug):
            print e
        return False

# determines what type of file we are dealing with
# recognizedTypes holds keywords (or key-fields) that identify
# a particular file.
# If forceType is set, it will match the only against that
# specific type and if it fails output information where the parsing
# failed (see matchFileAgainstKeywords())
def detFileType(fname, forceType = None):
    recognizedTypes = {}
    recognizedTypes["stat"] = \
        ["Holdings for", "fingerprint" + Word(hexnums) + ")", \
        "Your transactions since", "before your last STAT"]
    
    recognizedTypes["fund"] = \
        ["In order to make this deposit please send"]
    
    recognizedTypes["trade"] = \
        ["shares sold", "total value"] 

    if (forceType):
        if (matchFileAgainstKeywords(\
                fname, recognizedTypes[forceType], True)):
            return forceType
    else:
        for t in recognizedTypes.keys():
            if matchFileAgainstKeywords(fname, recognizedTypes[t]):
                return t
    
    # we couldn't match the file
    raise Exception("Could not determine the file type of " + fname)
    

# main function:
# determines the type of file, calls the respective parser
# and then processes the raw data into a nice output
def pyparse(fname = "", forceType = None):
    if forceType:
        ftype = forceType
    else:
        ftype = detFileType(fname, forceType)
    
    if ftype == "fund":
        p = getParser(getFundFields())
        tok = p.parseFile(fname)
        return {tok["address"]: Decimal(tok["ammount"])}

    elif ftype == "stat":
        p = getParser(getStatFields())
        tok = (p.parseFile(fname)).asDict()
        return parseStatTok(tok)

    elif ftype == "trade":
        p = getParser(getTradeFields())
        tok = (p.parseFile(fname))
        return {tok[2] : [Decimal(tok[1]), Decimal(tok[4]), Decimal(tok[6])]}
    
    else:
        print "Invalid file type"
        return

def parseStat(text):
    try:
        p = getParser(getStatFields())
        tok = (p.parseString(text)).asDict()
        res = parseStatTok(tok)
        return res                
    except ParseException, err:
        log.error("parseStat failed: %s", err)
        raise
def parseStatTok(tok):
    if tok.has_key("option_contracts"):
        tok["option_contracts"] = [[Decimal(t[0]), Decimal(t[2]), t[3]] for t in tok["option_contracts"]]
    
    if tok.has_key("current_holdings"):
        tok["current_holdings"] = \
            dict([ ( i["mpsic"] , Decimal(i["qty"]) ) for i in tok["current_holdings"] ])
        

    if tok.has_key("orders"):
        # mpexId : [mpsic,buysell,amount,unitprice]
        tok["orders"] = \
            dict([(i[8], {'mpsic':i[0], 'buysell':i[2], 'amount':Decimal(i[3]),'unitprice':Decimal(i[5]) }) for i in tok["orders"] ])
    else:
        tok["orders"] = dict()

    dateFormat = "%d %b %y %H %M %S"
    if tok.has_key("transactions"):
        #['Thu', ',', '19', 'Apr', '12', '12', ':', '03', ':', '48', '+/-', '0000']
        trans = []
        for el in tok["transactions"]:
            # raw date
            rd = el[1]
            #reconstruct original date
            dateString = ' '.join((rd[0]+rd[1],rd[2],rd[3],rd[4],rd[5]+rd[6]+rd[7]+rd[8]+rd[9],rd[10]+rd[11]))
            try:
                gd = parser.parse(dateString)
                trans.append({ 'date': gd, 
                        'mpsic': el[2],
                        'buysell': 'B' if el[5] == 'bought' else 'S', 
                        'amount' : Decimal(el[4]), 
                        'unitprice' : Decimal(el[6]), 
                        'total' : Decimal(el[8]) })
            except Exception as e:
                log.error(e)
                raise

        tok["transactions"] = trans
        tok["timestamp"] = datetime.datetime.fromtimestamp(int(tok['unixTimeStamp']))
    
    if tok.has_key("dividends"):
        divs = []
        for el in tok["dividends"]:
            #raw date
            rd = el[1]
            #reconstruct original date
            dateString = ' '.join((rd[0]+rd[1],rd[2],rd[3],rd[4],rd[5]+rd[6]+rd[7]+rd[8]+rd[9],rd[10]+rd[11]))
            try:
                gd = parser.parse(dateString)
                divs.append({ 'date': gd, 
                        'mpsic': el[3],
                        'amount' : Decimal(el[5]) })
            except Exception as e:
                log.error(e)
                raise
        tok["dividends"] = divs
    return tok
def parseDeposit(text):
    try:
        p = getParser(getFundFields())
        tok = (p.parseString(text)).asDict()
        return {"address" : tok["address"], "amount": Decimal(tok["ammount"])}
    except ParseException, err:
        log.error("parseDeposit failed: %s", err)
        raise
def parseOrder(text):
    try:
        p = getParser(getOrderFields())
        el = (p.parseString(text)).asList()
        #'Your order to' + (Literal('BUY') ^ 'SELL') + btcInt + mpsic + '@' + btcAmmount + 'BTC each has been received and will be processed'    
        return { 'mpsic': el[3],
                'buysell': 'B' if el[1] == 'BUY' else 'S', 
                'amount' : Decimal(el[2]), 
                'unitprice' : Decimal(el[5])
                }
    except ParseException, err:
        log.error("parseOrder failed: %s", err)
        raise
def parseExercise(text):
    try:
        p = getParser(getExerciseFields())
        tok = (p.parseString(text)).asDict()
        return {"mpsic" : tok["mpsic"], "total": Decimal(tok["total"]), "amount": int(tok["amount"])}
    except ParseException, err:
        log.error("parseExercise failed: %s", err)
        raise
if __name__ == '__main__':
    print "Data retrieved from " + sys.argv[1]
    y = pyparse(sys.argv[1])
    pp.pprint(y)
