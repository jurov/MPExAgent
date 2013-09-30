#!/usr/bin/python

import logging

if __name__ == '__main__':
    logging.basicConfig(filename='mpex.log',level=logging.DEBUG)

import gnupg
import urllib
import sys
import time,datetime
import hashlib
from twisted.internet import reactor
from twisted.web.client import Agent, HTTPConnectionPool
from twisted.web.http_headers import Headers
from twisted.web.client import FileBodyProducer
from StringIO import StringIO
from twisted.internet.protocol import Protocol
from twisted.internet.defer import Deferred
from pprint import pformat

log = logging.getLogger(__name__)

from gnupg import logger as gnupglogger
#gnupg likes to log sensitive material in debug mode
gnupglogger.setLevel(logging.INFO)

TIMEOUT = 120 # Last-resort timeout in seconds for the whole request
class StringRcv(Protocol):
    def __init__(self,finished,timeout = None):
        self.data = ''
        self.finished = finished
        self.timeout = timeout


    def dataReceived(self, bytes):
        self.data += bytes


    def connectionLost(self, reason):
        #log.debug('%s Data: %s', reason.value, self.data)
        if self.timeout:
            self.timeout.cancel()
        self.finished.callback(self.data)
class MPEx(object):
    testdata = None
    def __init__(self, debug=False, pool=None, mpexurl = 'http://mpex.co', **kwargs):
        self.gpg = gnupg.GPG()
        self.mpex_url = mpexurl
        self._mpex_fingerprint = 'A57D509A'
        self.passphrase = None
        self.debug = debug
        if(self.debug) :
            self.df = open("mpex_%d.txt" % time.time(),'w')
        self.agent = Agent(reactor, pool=pool, connectTimeout=TIMEOUT/3)


    def command(self, command):
        if (self.debug) :self.df.write(command)
        log.info("command('%s')",command)
        if (self.testdata):
            log.debug('returning testdata instead:%s',self.testdata)
            return self.testdata

        if self.passphrase == None: return None
        signed_data = str(self.gpg.sign(command, passphrase=self.passphrase))
        m = hashlib.md5()
        m.update(signed_data)
        md5d = m.hexdigest()
        log.debug('Signed:' + signed_data + "\nDigest/Track: " + md5d + "\n")
        encrypted_ascii_data = self.gpg.encrypt(str(signed_data), self.mpex_fingerprint(), passphrase=self.passphrase)
        data = urllib.urlencode({'msg' : str(encrypted_ascii_data)})
        body = FileBodyProducer(StringIO(data))
        d = self.agent.request(
            'POST',
            self.mpex_url,
            Headers({'Content-Type': ['application/x-www-form-urlencoded'], 
                #'Connection': ['Keep-Alive'] #redundant in HTTP/1.1
                }),
            body)
        def cbCommand(response):
            log.info('Response: %s %s %s', response.version, response.code, response.phrase)
            log.debug('Response headers: %s', pformat(list(response.headers.getAllRawHeaders())))
            finished = Deferred()
            timeout = reactor.callLater(TIMEOUT/2, finished.cancel)
            response.deliverBody(StringRcv(finished,timeout))
            finished.addCallback(self.decrypt, md5hash=md5d)
            return finished

        d.addCallback(cbCommand) 
        self.timeout = reactor.callLater(TIMEOUT, d.cancel)
        #TODO add retry in case of ResponseNeverReceived error, 
        #most likely caused by closing of persistent connection by server
        return d
    def decrypt(self,result,md5hash):
        if (self.debug) : 
            self.df.write(result)
            log.debug(result)
        reply = str(self.gpg.decrypt(result, passphrase=self.passphrase))
        if (self.debug) : 
            self.df.write(reply)
            self.df.flush()
        log.debug('decrypted reply:%s',reply)
        if not self.gpg.verify(reply):
            log.error('Invalid Signature,ignoring data!')
            reply = None
        if self.timeout.active():
            self.timeout.cancel()
        if reply == '': return None
        return dict(message=reply,md5hash=md5hash)
        
    def checkKey(self):
        keys = self.gpg.list_keys()
        for key in keys:
            if key['fingerprint'].endswith(self.mpex_fingerprint()):
                return True
        return False

    def mpex_fingerprint(self):
        """use/check current MPEx key depending on date"""
        return self._mpex_fingerprint
def _processReply(reply):
    if reply == None:
        print 'Couldn\'t decode the reply from MPEx, perhaps you didn\'t sign the key? try running'
        print 'gpg --sign-key F1B69921'
        exit()
    print reply
    
if __name__ == '__main__':
    from getpass import getpass
    mpex = MPEx(reactor,debug=True)
    if not mpex.checkKey():
        print 'You have not added MPExes keys. Please run...'
        print 'gpg --search-keys "F1B69921"'
        print 'gpg --sign-key F1B69921'
        exit()
    if len(sys.argv) != 2:
        print 'Usage: mpex.py <command>'
        print 'Example: mpex.py STAT'
        exit()
    mpex.passphrase = getpass("Enter your GPG passphrase: ")
    d = mpex.command(sys.argv[1])
    d.addCallback(_processReply)
    d.addCallback(lambda value: reactor.stop())
    d.addErrback(log.error)
    d.addErrback(lambda error : reactor.stop())
    reactor.run()
