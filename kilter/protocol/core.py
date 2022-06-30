# Copyright 2022 Dominik Sekotill <dom.sekotill@kodo.org.uk>
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

from typing import Iterable
from typing import Sequence
from warnings import warn

from . import messages
from .buffer import FixedSizeBuffer
from .exceptions import InvalidMessage
from .exceptions import NeedsMore
from .exceptions import UnexpectedMessage
from .exceptions import UnimplementedWarning


class Unimplemented(messages.BytesMessage, ident=b"\x00"):
	"""
	A message that has not been implemented by this package yet
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
	Unimplemented.ident: {messages.Continue.ident},
}

UPDATE_RESPONSES = {
	messages.ChangeHeader.ident,
	messages.AddHeader.ident,
	messages.InsertHeader.ident,
	messages.ChangeSender.ident,
	messages.AddRecipient.ident,
	messages.AddRecipientPar.ident,
	messages.RemoveRecipient.ident,
	messages.ReplaceBody.ident,
	messages.Progress.ident,
	messages.Quarantine.ident,
}


class FilterProtocol:
	"""
	The protocol state machine as seen from the side of a filter

	Low-level filter implementors should use this class to process messages to and from
	buffers.  The class checks the correctness of responses sent back to the MTA.
	"""

	def __init__(self, non_responders: Sequence[messages.Message] = []) -> None:
		self.nr = {m.ident for m in non_responders}
		self.state: tuple[messages.Message, set[bytes]]|None = None

	def read_from(self, buf: FixedSizeBuffer) -> Iterable[messages.Message]:
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
			except NotImplementedError as exc:
				if len(exc.args) != 1:
					raise
				data = exc.args[0]
				warn(UnimplementedWarning(f"unimplemented message: {data!r}"))
				message = Unimplemented(data)
				del buf[:len(data)]
			else:
				self._check_recv(message)
				yield message
				message.release()
				del buf[:size]

	def write_to(self, buf: FixedSizeBuffer, message: messages.Message) -> None:
		"""
		Validate and pack response and modification messages into a buffer
		"""
		self._check_send(message)
		message.pack(buf)

	def _check_recv(self, message: messages.Message) -> None:
		if isinstance(message, messages.Macro):
			return
		if isinstance(message, messages.Negotiate):
			self._store_mta_flags(message)
		if self.state is not None:
			raise UnexpectedMessage(message)
		try:
			responses = MTA_EVENT_RESPONSES[message.ident]
		except KeyError:
			raise InvalidMessage(message)
		if responses is None or message.ident in self.nr:
			return
		self.state = message, responses

	def _check_send(self, message: messages.Message) -> None:
		if self.state is None:
			raise UnexpectedMessage(message)
		if isinstance(message, messages.Negotiate):
			self._check_mta_flags(message)
		event, responses = self.state
		if message.ident in UPDATE_RESPONSES and isinstance(event, messages.EndOfMessage):
			return
		if message.ident not in responses:
			raise InvalidMessage(event, message)
		self.state = None

	def _store_mta_flags(self, message: messages.Negotiate) -> None:
		"""
		Store the option flags offered by an MTA for later checking
		"""

	def _check_mta_flags(self, message: messages.Negotiate) -> None:
		"""
		Check filter-requested option flags

		Filters cannot request options an MTA did not send, and any no-response (NR)
		flags need to be recorded for checking.
		"""
