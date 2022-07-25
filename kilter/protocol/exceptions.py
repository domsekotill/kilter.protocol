# Copyright 2022 Dominik Sekotill <dom.sekotill@kodo.org.uk>
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""
Exceptions raised by the package
"""

__all__ = [
	"InsufficientSpace", "NeedsMore", "UnexpectedMessage", "InvalidMessage",
	"UnimplementedWarning",
]


class InsufficientSpace(Exception):
	"""
	Raised to indicate that a complete message could not be written to a buffer
	"""


class NeedsMore(Exception):
	"""
	Raised to indicate that a complete message could not be extracted from a buffer
	"""


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


class UnimplementedWarning(Warning):
	"""
	Warning of an unknown message type
	"""
