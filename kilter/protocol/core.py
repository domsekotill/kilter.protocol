# Copyright 2022-2023 Dominik Sekotill <dom.sekotill@kodo.org.uk>
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""
State machines for the milter protocol

`FilterProtocol` is a state machine for the filter side of the milter protocol.
It is intended for validating messages, for example that responses are valid.
Choosing messages to transmit to an MTA is left to a higher level, as is handling I/O.
"""

from __future__ import annotations

from typing import Iterator
from typing import Sequence
from typing import TypeAlias
from typing import Union
from warnings import warn

from . import messages
from .buffer import FixedSizeBuffer
from .exceptions import InvalidMessage
from .exceptions import NeedsMore
from .exceptions import UnexpectedMessage
from .exceptions import UnknownMessage
from .messages import *

EventMessage: TypeAlias = Union[
	Connect,
	Helo,
	EnvelopeFrom,
	EnvelopeRecipient,
	Data,
	Unknown,
	Header,
	EndOfHeaders,
	Body,
	EndOfMessage,
	Macro,
	Abort,
]
"""
Messages sent from an MTA to a filter to indicate an event occurrence
"""

ResponseMessage: TypeAlias = Union[
	Continue,
	Reject,
	Discard,
	Accept,
	TemporaryFailure,
	ReplyCode,
]
"""
Messages send from a filter to an MTA in response to an `EventMessage`
"""

EditMessage: TypeAlias = Union[
	AddHeader,
	ChangeHeader,
	InsertHeader,
	ChangeSender,
	AddRecipient,
	AddRecipientPar,
	RemoveRecipient,
	ReplaceBody,
]
"""
Messages send from a filter to an MTA after an `EndOfMessage` to modify a message
"""

MTAMessage: TypeAlias = Union[
	EventMessage,
	Negotiate,
	Close,
]
"""
All messages that can be sent from an MTA to a filter
"""

FilterMessage: TypeAlias = Union[
	ResponseMessage,
	EditMessage,
	Negotiate,
	Skip,
]
"""
All messages that can be sent from a filter to an MTA
"""


MTA_EVENT_RESPONSES = {
	messages.Negotiate.ident: {
		messages.Negotiate.ident,
	},
	messages.Connect.ident: {
		messages.Continue.ident,
		messages.Reject.ident,
		messages.Accept.ident,
		messages.TemporaryFailure.ident,
	},
	messages.Helo.ident: {
		messages.Continue.ident,
		messages.Reject.ident,
		messages.Accept.ident,
		messages.TemporaryFailure.ident,
		messages.ReplyCode.ident,
	},
	messages.EnvelopeFrom.ident: {
		messages.Continue.ident,
		messages.Reject.ident,
		messages.Discard.ident,
		messages.Accept.ident,
		messages.ReplyCode.ident,
	},
	messages.EnvelopeRecipient.ident: {
		messages.Continue.ident,
		messages.Reject.ident,
		messages.Discard.ident,
		messages.Accept.ident,
		messages.TemporaryFailure.ident,
		messages.ReplyCode.ident,
	},
	messages.Data.ident: {
		messages.Continue.ident,
		messages.Reject.ident,
		messages.Discard.ident,
		messages.Accept.ident,
		messages.TemporaryFailure.ident,
		messages.ReplyCode.ident,
	},
	messages.Unknown.ident: {
		messages.Continue.ident,
		messages.Reject.ident,
		messages.Discard.ident,
		messages.Accept.ident,
		messages.TemporaryFailure.ident,
		messages.ReplyCode.ident,
	},
	messages.Header.ident: {
		messages.Continue.ident,
		messages.Reject.ident,
		messages.Discard.ident,
		messages.Accept.ident,
		messages.TemporaryFailure.ident,
		messages.ReplyCode.ident,
	},
	messages.EndOfHeaders.ident: {
		messages.Continue.ident,
		messages.Reject.ident,
		messages.Discard.ident,
		messages.Accept.ident,
		messages.TemporaryFailure.ident,
		messages.ReplyCode.ident,
	},
	messages.Body.ident: {
		messages.Continue.ident,
		messages.Reject.ident,
		messages.Discard.ident,
		messages.Accept.ident,
		messages.TemporaryFailure.ident,
		messages.Skip.ident,
		messages.ReplyCode.ident,
	},
	messages.EndOfMessage.ident: {
		messages.Continue.ident,
		messages.Reject.ident,
		messages.Discard.ident,
		messages.Accept.ident,
		messages.TemporaryFailure.ident,
		messages.ReplyCode.ident,
	},
	messages.Abort.ident: None,
	messages.Close.ident: None,
}

UPDATE_FLAG_MAP = {
	messages.ChangeHeader.ident:        ActionFlags.CHANGE_HEADERS,
	messages.AddHeader.ident:           ActionFlags.ADD_HEADERS,
	messages.InsertHeader.ident:        ActionFlags.ADD_HEADERS,
	messages.ChangeSender.ident:        ActionFlags.CHANGE_FROM,
	messages.AddRecipient.ident:        ActionFlags.ADD_RECIPIENT,
	messages.AddRecipientPar.ident:     ActionFlags.ADD_RECIPIENT_PAR,
	messages.RemoveRecipient.ident:     ActionFlags.DELETE_RECIPIENT,
	messages.ReplaceBody.ident:         ActionFlags.CHANGE_BODY,
	messages.Quarantine.ident:          ActionFlags.QUARANTINE,
}

NR_FLAG_MAP = {
	messages.Connect.ident:             ProtocolFlags.NR_CONNECT,
	messages.Helo.ident:                ProtocolFlags.NR_HELO,
	messages.EnvelopeFrom.ident:        ProtocolFlags.NR_SENDER,
	messages.EnvelopeRecipient.ident:   ProtocolFlags.NR_RECIPIENT,
	messages.Data.ident:                ProtocolFlags.NR_DATA,
	messages.Unknown.ident:             ProtocolFlags.NR_UNKNOWN,
	messages.Header.ident:              ProtocolFlags.NR_HEADER,
	messages.EndOfHeaders.ident:        ProtocolFlags.NR_EOH,
	messages.Body.ident:                ProtocolFlags.NR_BODY,
}


class FilterProtocol:
	"""
	The protocol state machine as seen from the side of a filter

	Low-level filter implementors should use this class to process messages to and from
	buffers.  The class checks the correctness of responses sent back to the MTA.
	"""

	def __init__(self) -> None:
		self.nr = set[bytes]()
		self.actions = set[bytes]([messages.Progress.ident])
		self.state: tuple[messages.Message, set[bytes]]|None = None
		self._optflags = ProtocolFlags(0)
		self._actflags = ActionFlags(0)

	def read_from(
		self,
		buf: FixedSizeBuffer,
	) -> Iterator[MTAMessage]:
		"""
		Return an iterator yielding each complete message from a buffer

		After each message is yielded the buffer is updated with the message content
		removed.  Messages that contain views of the buffer are released first, so if users
		wish to keep copies of any bytes data they must copy it before continuing the
		iterator.
		"""
		while 1:
			try:
				message, size = messages.Message.unpack(buf)
			except NeedsMore:
				return
			except UnknownMessage as exc:
				del buf[:len(exc.contents)]
				raise
			else:
				yield self._check_recv(message)
				message.release()
				del buf[:size]

	def write_to(
		self,
		buf: FixedSizeBuffer,
		message: FilterMessage,
	) -> None:
		"""
		Validate and pack response and modification messages into a buffer
		"""
		self._check_send(message)
		message.pack(buf)

	def _check_recv(self, message: messages.Message) -> Negotiate|EventMessage|Close:
		if isinstance(message, messages.Macro):
			return message
		if isinstance(message, messages.Negotiate):
			self._store_mta_flags(message)
		if self.state is not None:
			raise UnexpectedMessage(message)
		try:
			responses = MTA_EVENT_RESPONSES[message.ident]
		except KeyError:
			raise InvalidMessage(message)
		else:
			assert isinstance(
				message,
				(
					Negotiate, Macro, Connect, Helo, EnvelopeFrom, EnvelopeRecipient, Data,
					Unknown, Header, EndOfHeaders, Body, EndOfMessage, Abort, Close,
				),
			)
		if responses is not None and message.ident not in self.nr:
			self.state = message, responses
		return message

	def _check_send(self, message: messages.Message) -> None:
		if self.state is None:
			raise UnexpectedMessage(message)
		if isinstance(message, messages.Negotiate):
			self._check_mta_flags(message)
		event, responses = self.state
		if isinstance(event, messages.EndOfMessage):
			if message.ident in self.actions:
				return
			if message.ident in UPDATE_FLAG_MAP:
				raise UnexpectedMessage(message)
		if message.ident not in responses:
			raise InvalidMessage(message, event)
		self.state = None

	def _store_mta_flags(self, message: messages.Negotiate) -> None:
		"""
		Store the option flags offered by an MTA for later checking
		"""
		self._optflags = message.protocol_flags
		self._actflags = message.action_flags

	def _check_mta_flags(self, message: messages.Negotiate) -> None:
		"""
		Check filter-requested option flags

		Filters cannot request options an MTA did not send, and any no-response (NR)
		flags need to be recorded for checking.
		"""
		# ActionFlag.SETSYMLIST must be set if Negotiate.macros is not empty
		if message.macros:
			if ActionFlags.SETSYMLIST not in message.action_flags:
				message.action_flags |= ActionFlags.SETSYMLIST
				warn(f"adding {ActionFlags.SETSYMLIST!r} to {message}", stacklevel=4)
			if ActionFlags.SETSYMLIST not in self._actflags:
				raise ValueError("requesting symbols (macros) is not offered by the MTA")

		if (pflags := message.protocol_flags & ~self._optflags):
			raise ValueError(f"requested options not offered by the MTA: {pflags!r}")
		if (aflags := message.action_flags & ~self._actflags):
			raise ValueError(f"requested actions not offered by the MTA: {aflags!r}")
		self.nr.update(ident for ident, flag in NR_FLAG_MAP.items() if flag in message.protocol_flags)
		self.actions.update(ident for ident, flag in UPDATE_FLAG_MAP.items() if flag in message.action_flags)
