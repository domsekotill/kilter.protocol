# Copyright 2022-2023 Dominik Sekotill <dom.sekotill@kodo.org.uk>
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""
Exceptions raised by the package
"""

from typing import TYPE_CHECKING

__all__ = [
	"InsufficientSpace", "NeedsMore", "UnexpectedMessage", "InvalidMessage",
	"UnknownMessage",
]


class InsufficientSpace(Exception):
	"""
	Raised to indicate that a complete message could not be written to a buffer
	"""


class NeedsMore(Exception):
	"""
	Raised to indicate that a complete message could not be extracted from a buffer
	"""


class UnknownMessage(ValueError):
	"""
	Raised by the message unpacker to indicate that it lacks a class for the message

	The first (and only) argument to the exception is the message that could not be
	unpacked.
	"""

	if TYPE_CHECKING:
		def __init__(self, message: bytes): ...

	def __str__(self) -> str:  # pragma: no-cover
		contents = self.contents
		message = f"{contents[:50]!r} (trimmed)" if len(contents) > 50 else repr(contents)
		return f"unknown message: {message}"

	@property
	def contents(self) -> bytes:
		"""
		The byte string that could not be unpacked
		"""
		assert isinstance(self.args[0], bytes)
		return self.args[0]


class UnexpectedMessage(TypeError):
	"""
	Raised by a protocol to indicate a message that is not expected in the current state
	"""

	def __str__(self) -> str:
		return f"message was not expected by the protocol: {self.args[0]}"


class InvalidMessage(UnexpectedMessage):
	"""
	Raised by a protocol to indicate a message that is unknown to the state machine
	"""
