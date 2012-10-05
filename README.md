MPExAgent
=========

It allows you to access MPEx by any JSONRPC-capable application, from local or 
remote  machine. MPEx replies for all supported commands are extracted and parsed into 
easily processable form.

*Warning: This MPExAgent version does not support any authentication! Anyone 
who has access to the listening port, can freely issue MPEx commands in your name. Try it only behind firewall.
Patches to support HTTP authentication (should not be hard to add, twisted supports it) or other means are 
welcome.*

#Install/usage

##Dependencies:
* python_gnupg
* Twisted
* DateUtils 
* pyparsing
* jsonrpc

If using virtualenv, this will install them all:

easy_install python_gnupg Twisted DateUtils pyparsing jsonrpc

##Running the agent
It expects/uses current user's default GPG key in exactly the same way as pyMPEx. If you 
successfully accessed MPEx using pyMPEx, the agent should work out of the box.

In the bottom of agent.py, there is port setting

PORT = 8007

This sets the HTTP/JSONRPC listening port. 

Run ./mpexagent.py . It will ask for your GPG passphrase. While it is running, the 
passphrase will stay cached in memory. It keeps running in foreground, daemon mode is not 
supported yet.

##Accessing the agent

The listening port is configured above, and default path for submitting JSONRPC calls is /jsonrpc .

Using Python : see sampleclient.py

##Input/Output format
Output JSON structure for all supported commands is documented in agent.py. 
Supported functions are at the moment (lowercase):
* stat
* deposit
* neworder
* exercise
* cancel

With exception of neworder, the functions accept exactly the same arguments in 
same order as their MPEx counterparts. neworder has first parameter 'B' or 'S' 
to indicate order type, following parameters are the same as MPEx BUY/SELL command.

To ease JSON processing, following minor updates are done to output data:
* all bitcoin amounts are converted to satoshi to avoid floating point conversion/rounding.
  (FYI: Bitcoind RPC solves this by parsing all numbers into Decimals, but this requires customized JSON 
  parser at the receiving side, that isn't always practical.)
* all dates are converted into strings using ISO format (using isoformat()). 
  sampleclient.py converts them back to Python dates in deserializeStat().

