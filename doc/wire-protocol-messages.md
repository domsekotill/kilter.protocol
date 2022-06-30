Wire Protocol Messages
======================

Messages use a simple format, that starts with the same two fields (in network byte order, 
obviously):

- `unsigned long`: message size (excluding this field, including command octet)
- `char`: A type value, see the message sections below for each type's value.

The rest of the message, if there is any, is type-dependent and described in the relevant 
section below.

```{contents}
:local:
```


MTA Setup Commands
------------------

### Negotiate

Sent by an MTA after connecting to the filter to indicate its accepted options and returned 
with modified options by the filter.

Optional symbol lists (macros) may be requested for each supported event.  The event is 
signaled with an `unsigned long integer` value that maps to an event message type but is 
unrelated to the message's identifier (`char`). Note that not all events can have macros 
send with them. The symbols are delivered with a [Macro](#macro) message before the relevant 
event message.

| Stage | Event Message                             |
| ----- | ----------------------------------------- |
|   0   | [Connect](#connect)                       |
|   1   | [Helo](#helo)                             |
|   2   | [Envelope From](#envelope-from)           |
|   3   | [Envelope Recipient](#envelope-recipient) |
|   4   | [Data](#data)                             |
|   5   | [End of Message](#end-of-message)         |
|   6   | [End of Headers](#end-of-headers)         |

*This message corresponds to the {{ libmilter }} callback [xxfi_negotiate][]
 registered with [smfi_register][].*

**Class:** {py:class}`kilter.protocol.messages.Negotiate`\
**Type Value:** `'O'`\
**Responses:**
  [Negotiate](#negotiate)\
**Data Structure:**

```C
struct {
  unsigned long version;
  unsigned long action_flags;    /* bit-field */
  unsigned long protocol_flags;  /* bit-field */
  struct {
    unsigned long stage;
    char symbols[]; /* NULL-terminated, space-separated names */
  }[];
};
```

---

### Macro

Transfer symbol (macro) values to a filter for the subsequent [event 
message](#event-messages).  There is no response expected.  The event is indicated with 
a `char` type value.

**Type Value:** `'D'`
**Data Structure:**

```C
struct {
  char event;
  struct {
    char symbol[];  /* NULL-terminated string */
    char value[];  /* NULL-terminated string */
  }[];
};
```


---

Event Messages
--------------

These messages are sent with event-appropriate data from the MTA to indicate an event 
occurring that the filter previously registered its interest in.

### Connect

Sent when a client connects to the MTA.

*This event corresponds to the {{ libmilter }} callback [xxfi_connect][]
 registered with [smfi_register][].*

**Class:** {py:class}`kilter.protocol.messages.Connect`\
**Type Value:** `'C'`\
**Responses:**
  [Continue](#continue), [Reject](#reject), [Accept](#accept),
  [Temporary Failure](#temporary-failure)\
**Data Structure:**

```C
struct {
  char hostname[];  /* NULL-terminated string */
  char addr_family;
  union {
    /* addr_family == Family.UNKNOWN */
    struct {} unknown;

    /* addr_family in {Family.INET, Family.INET6, Family.UNIX} */
    struct {
      unsigned short port;
      char address[];  /* NULL-terminated string */
    } known;
  };
};
```

---

### Helo

Sent when a client transfers a HELO or EHLO command.

*This event corresponds to the {{ libmilter }} callback [xxfi_helo][]
 registered with [smfi_register][].*

**Class:** {py:class}`kilter.protocol.messages.Helo`\
**Type Value:** `'H'`\
**Responses:**
  [Continue](#continue), [Reject](#reject), [Accept](#accept),
  [Temporary Failure](#temporary-failure), [Reply Code](#reply-code)\
**Data Structure:**

```C
char hostname[];  /* NULL-terminated string */
```

---

### Envelope From

Sent when a client transfers a "MAIL FROM" command.

*This event corresponds to the {{ libmilter }} callback [xxfi_envfrom][]
 registered with [smfi_register][].*

**Class:** {py:class}`kilter.protocol.messages.EnvelopeFrom`\
**Type Value:** `'K'`\
**Responses:**
  [Continue](#continue), [Reject](#reject), [Discard](#discard), [Accept](#accept),
  [Reply Code](#reply-code)\
**Data Structure:**

```C
struct {
  char sender[];  /* NULL-terminated string */
  char argv[][];  /* Sequence of NULL-terminated strings */
}
```

---

### Envelope Recipient

Sent when a client indicates a recipient with an "RCPT TO" command.

*This event corresponds to the {{ libmilter }} callback [xxfi_envrcpt][]
 registered with [smfi_register][].*

**Class:** {py:class}`kilter.protocol.messages.EnvelopeRecipient`\
**Type Value:** `'R'`\
**Responses:**
  [Continue](#continue), [Reject](#reject), [Discard](#discard), [Accept](#accept),
  [Temporary Failure](#temporary-failure), [Reply Code](#reply-code)\
**Data Structure:**

```C
struct {
  char sender[];  /* NULL-terminated string */
  char argv[][];  /* Sequence of NULL-terminated strings */
}
```

---

### Data

Sent when a client indicates it wants to send a message with the DATA command.

This would indicate the end of envelope recipients.

*This event corresponds to the {{ libmilter }} callback [xxfi_data][]
 registered with [smfi_register][].*

**Class:** {py:class}`kilter.protocol.messages.Data`\
**Type Value:** `'T'`\
**Responses:**
  [Continue](#continue), [Reject](#reject), [Discard](#discard), [Accept](#accept),
  [Temporary Failure](#temporary-failure), [Reply Code](#reply-code)\
**Data Structure:** *None*

---

### Unknown

Sent when a client tries to use an SMTP command that is unknown to the MTA

*This event corresponds to the {{ libmilter }} callback [xxfi_unknown][]
 registered with [smfi_register][].*

**Class:** {py:class}`kilter.protocol.messages.Unknown`\
**Type Value:** `'U'`\
**Responses:**
  [Continue](#continue), [Reject](#reject), [Discard](#discard), [Accept](#accept),
  [Temporary Failure](#temporary-failure), [Reply Code](#reply-code)\
**Data Structure:**

```C
char* contents;  /* NULL-terminated string */
```

---

### Header

Sent for each mail header that arrives in a message.

*This event corresponds to the {{ libmilter }} callback [xxfi_header][]
 registered with [smfi_register][].*

**Class:** {py:class}`kilter.protocol.messages.Header`\
**Type Value:** `'L'`\
**Responses:**
  [Continue](#continue), [Reject](#reject), [Discard](#discard), [Accept](#accept),
  [Temporary Failure](#temporary-failure), [Reply Code](#reply-code)\
**Data Structure:**

```C
struct {
  char name[];   /* NULL-terminated string */
  char value[];  /* NULL-terminated string */
}
```

---

### End of Headers

Sent once all message headers have been processed.

*This event corresponds to the {{ libmilter }} callback [xxfi_eoh][]
 registered with [smfi_register][].*

**Class:** {py:class}`kilter.protocol.messages.EndOfHeaders`\
**Type Value:** `'N'`\
**Responses:**
  [Continue](#continue), [Reject](#reject), [Discard](#discard), [Accept](#accept),
  [Temporary Failure](#temporary-failure), [Reply Code](#reply-code)\
**Data Structure:** *None*

---

### Body

Transfer a chunk of a message body to a filter.

Although each SMTP message is transfered to the MTA in one continuous stream, it is passed 
as chunks in Body messages.  This allows [Skip](#skip) (or any other non-Continue response) 
to be sent as a response once the filter has seen enough of the message body to satisfy its 
interest.

*This event corresponds to the {{ libmilter }} callback [xxfi_body][]
 registered with [smfi_register][].*

**Class:** {py:class}`kilter.protocol.messages.Body`\
**Type Value:** `'B'`\
**Responses:**
  [Continue](#continue), [Reject](#reject), [Discard](#discard), [Accept](#accept),
  [Temporary Failure](#temporary-failure), [Skip](#skip), [Reply Code](#reply-code)\
**Data Structure:**

```C
char *content;  /* unterminated; xxfi_body requires a length argument */
```

---

### End of Message

*A.K.A. End of Body*

Similar to [Body](#body) although only for the final chunk.  While its awaiting a response 
to this event, is the only time an MTA will accept [modifications](#modification-messages).

> **TODO**
> What is sent if a Skip response is previously returned?

*This event corresponds to the {{ libmilter }} callback [xxfi_eom][]
 registered with [smfi_register][].*

**Class:** {py:class}`kilter.protocol.messages.EndOfMessage`\
**Type Value:** `'E'`\
**Responses:**
  [Continue](#continue), [Reject](#reject), [Discard](#discard), [Accept](#accept),
  [Temporary Failure](#temporary-failure), [Reply Code](#reply-code)\
**Data Structure:**

```C
char *content;  /* unterminated; xxfi_body requires a length argument */
```

---

### Abort

Tell the filter the session has been aborted.

*This event corresponds to the {{ libmilter }} callback [xxfi_abort][]
 registered with [smfi_register][].*

**Class:** {py:class}`kilter.protocol.messages.Abort`\
**Type Value:** `'A'`\
**Responses:** *None*\
**Data Structure:** *None*

---

### Close

Sent when a client sends a QUIT command.

*This event corresponds to the {{ libmilter }} callback [xxfi_close][]
 registered with [smfi_register][].*

**Class:** {py:class}`kilter.protocol.messages.Close`\
**Type Value:** `'Q'`\
**Responses:** *None*\
**Data Structure:** *None*

---

### QUIT with New Connection

???

**Type Value:** `'K'`


---

Response Messages
-----------------

The messages are sent from the filter to indicate a response to an event, and are required 
before the MTA will send further events.  After sending, no further messages may be sent by 
a filter until a new event is received from the MTA.

### Continue

Continue processing a connection, message or recipient

**Class:** {py:class}`kilter.protocol.messages.Continue`\
**Type Value:** `'c'`\
**Negotiated:** no\
**Events:**
  [Connect](#connect), [Helo](#helo), [Envelope-From](#envelope-from),
  [Envelope-Recipient](#envelope-recipient), [Data](#data), [Unknown](#unknown),
  [Header](#header), [End-of-Headers](#end-of-headers),
  [Body](#body), [End-of-Message](#end-of-message), [Abort](#abort), [Close](#close),
  [Negotiate](#negotiate)

---

### Reject

Reject a connection, message, or recipient

**Class:** {py:class}`kilter.protocol.messages.Reject`\
**Type Value:** `'r'`\
**Negotiated:** no\
**Events:**
  [Connect](#connect), [Helo](#helo), [Envelope-From](#envelope-from),
  [Envelope-Recipient](#envelope-recipient), [Data](#data), [Unknown](#unknown),
  [Header](#header), [End-of-Headers](#end-of-headers),
  [Body](#body), [Negotiate](#negotiate)

---

### Discard

Tell the MTA to appear to accept a message or recipient, but reject it internally.

**Class:** {py:class}`kilter.protocol.messages.Discard`\
**Type Value:** `'d'`\
**Negotiated:** no\
**Events:**
  [Envelope-From](#envelope-from), [Envelope-Recipient](#envelope-recipient), [Data](#data),
  [Unknown](#unknown), [Header](#header), [End-of-Headers](#end-of-headers),
  [Body](#body), [End-of-Message](#end-of-message), [Abort](#abort)

---

### Accept

Accept a connection, message or recipient and skip further filtering.

**Class:** {py:class}`kilter.protocol.messages.Accept`\
**Type Value:** `'a'`\
**Negotiated:** no\
**Events:**
  [Connect](#connect), [Helo](#helo), [Envelope-From](#envelope-from),
  [Envelope-Recipient](#envelope-recipient), [Data](#data), [Unknown](#unknown),
  [Header](#header), [End-of-Headers](#end-of-headers),
  [Body](#body), [End-of-Message](#end-of-message), [Abort](#abort), [Negotiate](#negotiate)

---

### Temporary Failure

Similar to Reject, however an SMTP temporary failure code (4xx) will be returned.

**Class:** {py:class}`kilter.protocol.messages.TemporaryFailure`\
**Type Value:** `'t'`\
**Negotiated:** no\
**Events:**
  [Connect](#connect), [Helo](#helo), [Envelope-Recipient](#envelope-recipient),
  [Data](#data), [Unknown](#unknown), [Header](#header), [End-of-Headers](#end-of-headers),
  [Body](#body), [End-of-Message](#end-of-message), [Abort](#abort), [Negotiate](#negotiate)

---

### Skip

Used to skip further Body events if a filter has processed enough of a message body to make 
a decision and wants to move onto the End-of-Message event.

**Class:** {py:class}`kilter.protocol.messages.Skip`\
**Type Value:** `'s'`\
**Negotiated:** yes\
**Events:**
  [Body](#body)

---

### Reply Code

Return arbitrary 4xx and 5xx return codes and messages.  This is the only response code with 
attached data.

**Class:** {py:class}`kilter.protocol.messages.ReplyCode`\
**Type Value:** `'y'`\
**Negotiated:** no\
**Events:**
  [Helo](#helo), [Envelope-From](#envelope-from), [Envelope-Recipient](#envelope-recipient),
  [Data](#data), [Unknown](#unknown), [Header](#header), [End-of-Headers](#end-of-headers),
  [Body](#body), [End-of-Message](#end-of-message), [Abort](#abort), [Negotiate](#negotiate)


---

Modification Messages
---------------------

These messages are sent by the filter to request a modification of a message, and MAY ONLY 
be sent after receiving an End-of-Message event from the MTA, and before sending a response 
for that event.  To be send they MUST have been enabled during filter registration.

### Add Header

Add a header to the message

*This command corresponds to the [smfi_addheader][] function in {{ libmilter }}*

**Class:** {py:class}`kilter.protocol.messages.AddHeader`\
**Type Value:** `'h'`\
**Data Structure:**

```C
struct {
  char field[];  /* NULL-terminated string */
  char value[];  /* NULL-terminated string */
};
```

---

### Change Header

Change or delete an existing header in the message

*This command corresponds to the [smfi_chgheader][] function in {{ libmilter }}*

**Class:** {py:class}`kilter.protocol.messages.ChangeHeader`\
**Type Value:** `'m'`\
**Data Structure:**

```C
struct {
  unsigned long index;
  char field[];  /* NULL-terminated string */
  char value[];  /* NULL-terminated string */
};
```

---

### Insert Header

Insert a header at a given position in the header list

*This command corresponds to the [smfi_insheader][] function in {{ libmilter }}*

**Class:** {py:class}`kilter.protocol.messages.InsertHeader`\
**Type Value:** `'i'`\
**Data Structure:**

```C
struct {
  unsigned long index;
  char field[];  /* NULL-terminated string */
  char value[];  /* NULL-terminated string */
};
```

---

### Change Sender

Change the envelope sender address.

*This command corresponds to the [smfi_chgfrom][] function in {{ libmilter }}*

**Class:** {py:class}`kilter.protocol.messages.ChangeSender`\
**Type Value:** `'e'`
**Data Structure:**

```C
union {
  struct {
    char address[];  /* NULL-terminated RFC-6530 address */
  } without_args;
  struct {
    char address[];  /* NULL-terminated RFC-6530 address */
    char args[];  /* NULL-terminated string */
  } with_args;
};
```

---

### Add Recipient

Add a recipient to a message

*This command corresponds to the [smfi_addrcpt][] function in {{ libmilter }}*

**Class:** {py:class}`kilter.protocol.messages.AddRecipient`\
**Type Value:** `'+'`\
**Data Structure:**

```C
char address[];  /* NULL-terminated RFC-6530 address */
```

---

### Add Recipient (with ESMTP arguments)

Add a recipient to a message with additional ESMTP arguments appended.

*This command corresponds to the [smfi_addrcpt_par][] function in {{ libmilter }}*

**Class:** {py:class}`kilter.protocol.messages.AddRecipientPar`\
**Type Value:** `'2'`\
**Data Structure:**

```C
struct {
  char address[];  /* NULL-terminated RFC-6530 address */
  char args[];  /* NULL-terminated string */
};
```

---

### Remove Recipient

Remove a recipient from a message (similar to returning [Discard](#discard) in response to 
an [Envelope-Recipient](#envelope-recipient) event).

*This command corresponds to the [smfi_delrcpt][] function in {{ libmilter }}*

**Class:** {py:class}`kilter.protocol.messages.RemoveRecipient`\
**Type Value:** `'-'`\
**Data Structure:**

```C
char address[];  /* NULL-terminated RFC-6530 address */
```

---

### Replace Body

Replace the body of a message.  The first message causes the original body to be truncated, 
and each replacement message is then appended to the message.

*This command corresponds to the [smfi_replacebody][] function in {{ libmilter }}*

**Class:** {py:class}`kilter.protocol.messages.ReplaceBody`\
**Type Value:** `'b'`\
**Data Structure:**

```C
char *content;  /* unterminated; smfi_replacebody requires a length argument */
```

---

### Progress

Indicates that the filter is still processing a message, used to prevent an MTA from 
treating a filter as stuck.

*This command corresponds to the [smfi_progress][] function in {{ libmilter }}*

**Class:** {py:class}`kilter.protocol.messages.Progress`\
**Type Value:** `'p'`\
**Data Structure:** *None*

---

### Quarantine

Request that the MTA quarantines a message, with a reason.

*This command corresponds to the [smfi_quarantine][] function in {{ libmilter }}*

**Class:** {py:class}`kilter.protocol.messages.Quarantine`\
**Type Value:** `'q'`\
**Data Structure:**

```C
char reason[];  /* NULL-terminated free-form message */
```


---

Misc Messages
-------------

These messages appear to be unused or are internal to {{ libmilter }}.

### Shutdown

**Type Value:** `'4'`

---

### Connection Fail

Cause a connection failure (between the MTA and client, presumably).

**Type Value:** `'f'`

---

### Set Symbol List

Change the requested symbol list to receive from the MTA?

**Type Value:** `'l'`



[smfi_register]:
  https://pythonhosted.org/pymilter/milter_api/smfi_register.html

[smfi_addheader]:
  https://pythonhosted.org/pymilter/milter_api/smfi_addheader.html

[smfi_chgheader]:
  https://pythonhosted.org/pymilter/milter_api/smfi_chgheader.html

[smfi_insheader]:
  https://pythonhosted.org/pymilter/milter_api/smfi_insheader.html

[smfi_chgfrom]:
  https://pythonhosted.org/pymilter/milter_api/smfi_chgfrom.html

[smfi_addrcpt]:
  https://pythonhosted.org/pymilter/milter_api/smfi_addrcpt.html

[smfi_addrcpt_par]:
  https://pythonhosted.org/pymilter/milter_api/smfi_addrcpt_par.html

[smfi_delrcpt]:
  https://pythonhosted.org/pymilter/milter_api/smfi_delrcpt.html

[smfi_replacebody]:
  https://pythonhosted.org/pymilter/milter_api/smfi_replacebody.html

[smfi_progress]:
  https://pythonhosted.org/pymilter/milter_api/smfi_progress.html

[smfi_quarantine]:
  https://pythonhosted.org/pymilter/milter_api/smfi_quarantine.html

[xxfi_negotiate]:
  https://pythonhosted.org/pymilter/milter_api/xxfi_negotiate.html

[xxfi_connect]:
  https://pythonhosted.org/pymilter/milter_api/xxfi_connect.html

[xxfi_helo]:
  https://pythonhosted.org/pymilter/milter_api/xxfi_helo.html

[xxfi_data]:
  https://pythonhosted.org/pymilter/milter_api/xxfi_data.html

[xxfi_unknown]:
  https://pythonhosted.org/pymilter/milter_api/xxfi_unknown.html

[xxfi_envfrom]:
  https://pythonhosted.org/pymilter/milter_api/xxfi_envfrom.html

[xxfi_envrcpt]:
  https://pythonhosted.org/pymilter/milter_api/xxfi_envrcpt.html

[xxfi_header]:
  https://pythonhosted.org/pymilter/milter_api/xxfi_header.html

[xxfi_eoh]:
  https://pythonhosted.org/pymilter/milter_api/xxfi_eoh.html

[xxfi_body]:
  https://pythonhosted.org/pymilter/milter_api/xxfi_body.html

[xxfi_eom]:
  https://pythonhosted.org/pymilter/milter_api/xxfi_eom.html

[xxfi_abort]:
  https://pythonhosted.org/pymilter/milter_api/xxfi_abort.html

[xxfi_close]:
  https://pythonhosted.org/pymilter/milter_api/xxfi_close.html
