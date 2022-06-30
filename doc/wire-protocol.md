Milter API Protocol
===================

A Mail Transfer Agent (MTA) communicates with a mail filter by connecting to a stream port.
The format of the messages transfered are described in 
[Wire Protocol Messages](wire-protocol-messages.md).

```{toctree}
:maxdepth: 2

wire-protocol-messages
```

Background
----------

Mail transport is complex and MTAs typically only concern themselves with co-ordinating the 
movement of mail.  However there are a great many other aspects of mail transport that 
a well configured mail network needs to integrate.  These additional behaviours can be added 
as filter microservices.  Sendmail originally created a protocol and library to simplify 
implementing these microservices, which Postfix and others later reverse engineered to 
support the same filters (known as "milters").

MTAs are configured to connect to the filters when a peer connects, negotiate the features 
the filter wants to use, and start sending event messages to the filter at various points of 
the mail transport session.  The filter may then indicate, by returning response messages, 
what actions the MTA should take.  At the end of the session the filter may also modify the 
message if it wishes by sending modification messages.

Contact with the filter requires a stream communication channel, for instance TCP when 
communicating over IP addressed networks.  Typically TCP is used for a distributed 
microservice architecture or Unix stream sockets for local filter services; however any 
bi-directional stream could be used, for instance process pipes.


Negotiation
-----------

The first step after connecting is to [negotiate](wire-protocol-messages.md#negotiate) the 
events the filter wants to be notified of (thus avoiding unnecessary communication) and the 
features it wishes to use.  Not all features will be implemented by all MTAs, so filters may 
need to work around missing features, or indicate to users that there is an unresolvable 
problem and quit.


Events
------

The events that filters can request cover:

- transport related events, i.e. connect, close
- various SMTP commands from the peer
- receipt of each message header
- receipt of chunks of the message body

In response to any event the filter can indicate if it wishes to continue or finish 
processing the current message, and either accept or reject the message.  There are several 
types of rejection.

In addition, in response to each chunk received of the message body, the filter may indicate 
that it wishes to continue but skip the rest of the body.


Modification
------------

After receiving the final message event 
([End of Message](wire-protocol-messages.md#end-of-message)) but before returning a response 
to it, the filter may choose to modify the message.  This must be negotiated beforehand.  
Filters can modify envelope addresses, message headers, and the entire message body.
