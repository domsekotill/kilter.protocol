# Copyright 2022 Dominik Sekotill <dom.sekotill@kodo.org.uk>
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""
Classes for representing protocol messages, and packing and unpacking them

Most users of classes in this module will only be interested in their use as data-classes;
leaving packing and unpacking to a separate module.  See `Message` for details of packing
and unpacking.
"""

from __future__ import annotations

from abc import ABCMeta
from abc import abstractmethod
from collections.abc import Collection
from collections.abc import Iterable
from collections.abc import Iterator
from collections.abc import Mapping
from dataclasses import dataclass
from dataclasses import field
from enum import Enum
from ipaddress import IPv4Address
from ipaddress import IPv6Address
from ipaddress import ip_address
from pathlib import Path
from struct import Struct
from typing import TYPE_CHECKING
from typing import ClassVar
from typing import TypeVar
from typing import cast

from .exceptions import InsufficientSpace
from .exceptions import NeedsMore

if TYPE_CHECKING:
	from .buffer import FixedSizeBuffer

LONG = Struct("!L")

__all__ = [
	"Family", "Stage", "BitField", "ActionFlags", "ProtocolFlags",
	"Message", "Negotiate", "Macro", "Connect", "Helo", "EnvelopeFrom",
	"EnvelopeRecipient", "Data", "Unknown", "Header", "EndOfHeaders", "Body",
	"EndOfMessage", "Abort", "Close", "Continue", "Reject", "Discard", "Accept",
	"TemporaryFailure", "Skip", "ReplyCode", "ChangeHeader", "Quarantine",
	"AddHeader", "InsertHeader", "ChangeSender", "AddRecipient", "AddRecipientPar",
	"RemoveRecipient", "ReplaceBody", "Progress",
]


def split_cstring(buf: memoryview) -> tuple[memoryview, memoryview]:
	"""
	Split a memoryview at a NULL byte, into a view of the pre-NULL string, and the remainder
	"""
	for i, c in enumerate(buf):
		if c == 0:
			return buf[:i], buf[i+1:]
	raise ValueError("missing NULL termination byte")


def write_cstring(buf: FixedSizeBuffer, string: bytes) -> None:
	"""
	Write a byte string to a buffer and append a NULL-terminator
	"""
	buf[:] = string
	buf[:] = b"\x00"


def cstring_iter(buf: memoryview) -> Iterator[memoryview]:
	"""
	Return an iterator that yields NULL-terminated substrings from a memoryview

	The yielded strings do not have the NULL-terminator
	"""
	while len(buf) > 0:
		string, buf = split_cstring(buf)
		yield string


class Family(bytes, Enum):
	"""
	BSD socket address families (of MTA clients) supported by the protocol
	"""

	UNKNOWN = b"U"
	UNIX = b"L"
	INET = b"4"
	INET6 = b"6"


class Stage(int, Enum):
	"""
	Stages that support macro (symbol) lists, for `Negotiate` messages

	Each stage corresponds to an event `Message`, although not every event is a stage.

	The values of the stages do not correspond to `Message.ident` values.  It is left to
	implementors creating `Negotiate` messages to implement the mapping, if needed.
	"""

	CONNECT = 0
	HELO = 1
	ENVELOPE_FROM = 2
	ENVELOPE_RECIPIENT = 3
	DATA = 4
	END_MESSAGE = 5
	END_HEADERS = 6


BFSelf = TypeVar("BFSelf", bound="BitField")


class BitField(int, Enum):
	"""
	Base class for bit-field enums like ActionFlags and ProtocolFlags
	"""

	@classmethod
	def pack(cls: type[BFSelf], flags: Iterable[BFSelf]) -> int:
		rflag = 0
		for flag in flags:
			rflag |= flag
		return rflag

	@classmethod
	def unpack(cls: type[BFSelf], bitfield: int) -> set[BFSelf]:
		return {flag for flag in cls if flag & bitfield}


class ActionFlags(BitField):
	"""
	Bit-field values for the `Negotiate.action_flags` field of the `Negotiate` message

	The values correspond to the `SPFIF_*` codes as described in
	https://pythonhosted.org/pymilter/milter_api/smfi_register.html#flags
	"""

	ADD_HEADERS = ADDHDRS = 0x1
	CHANGE_HEADERS = CHGHDRS = 0x10
	CHANGE_BODY = CHGBODY = 0x2
	ADD_RECIPIENT = ADDRCPT = 0x4
	ADD_RECIPIENT_PAR = ADDRCPT_PAR = 0x80
	DELETE_RECIPIENT = DELRCPT = 0x8
	QUARANTINE = 0x20
	CHANGE_FROM = CHGFROM = 0x40
	SETSYMLIST = 0x100


class ProtocolFlags(BitField):
	"""
	Bit-field values for the `Negotiate.protocol_flags` field of the `Negotiate` message

	The values correspond to the `SMFIP_*` codes described in
	https://pythonhosted.org/pymilter/milter_api/xxfi_negotiate.html
	"""

	NO_CONNECT = 0x1
	NO_HELO = 0x2
	NO_SENDER = NO_MAIL = 0x4
	NO_RECIPIENT = NO_RCPT = 0x8
	NO_BODY = 0x10
	NO_HEADERS = NO_HDRS = 0x20
	NO_END_OF_HEADERS = NO_EOH = 0x40
	NO_UNKNOWN = 0x100
	NO_DATA = 0x200

	SKIP = 0x400

	REJECTEDT_RECIPIENT = RCPT_REJ = 0x800

	NR_CONNECT = NR_CONN = 0x1000
	NR_HELO = 0x2000
	NR_SENDER = NR_MAIL = 0x4000
	NR_RECIPIENT = NR_RCPT = 0x8000
	NR_DATA = 0x10000
	NR_UNKNOWN = NR_UNKN = 0x20000
	NR_END_OF_HEADERS = NR_EOH = 0x40000
	NR_BODY = 0x80000
	NR_HEADER = NR_HDR = 0x80

	HEADER_LEADING_SPACE = HDR_LEADSPC = 0x100000

	MAX_DATA_SIZE_256K = MDS_256K = 0x10000000
	MAX_DATA_SIZE_1M = MDS_1M = 0x20000000


class Message(metaclass=ABCMeta):
	r"""
	A base class for all messages which also handles packing and unpacking messages

	Unpacking messages from a `kilter.protocol.buffer.FixedSizeBuffer` uses the
	`Message.unpack` class method:

	>>> from kilter.protocol.buffer import SimpleBuffer
	>>> from kilter.protocol.messages import Message
	>>> buf = SimpleBuffer(1024)
	>>> buf[:] = b"\x00\x00\x00\x0dHexample.com\x00"
	>>> Message.unpack(buf)
	(Helo(hostname='example.com'), 17)

	Packing messages into a buffer is done with the `Message.pack` method, available to all
	instances:

	>>> from ipaddress import IPv4Address
	>>> from kilter.protocol.messages import Connect
	>>> buf = SimpleBuffer(1024)
	>>> message = Connect("example.com", IPv4Address("10.0.0.1"), 25025)
	>>> message.pack(buf)
	>>> buf[:].tobytes()
	b'\x00\x00\x00\x19Cexample.com\x004a\xc110.0.0.1\x00'

	Note that messages unpacked from a buffer may hold memoryviews of the buffer.  This
	means that *(a)* if the buffer contents are overwritten the message's data may be
	affected, and *(b)* the buffer cannot be resized without calling the message's
	`Message.release` method first.  For these reasons users should ensure that before
	updating the buffer with new data, each message is processed, any needed data is
	copied, and the message's `release` method is called.

	>>> buf[0:] = b"\x00\x00\x00\x12Mtest@example.com\x00"
	>>> message, _ = Message.unpack(buf)
	>>> del buf[:10]
	Traceback (most recent call last):
		...
	BufferError: Existing exports of data: object cannot be re-sized
	>>> message.release()
	>>> del buf[:10]
	"""

	if TYPE_CHECKING:
		Self = TypeVar("Self", bound="Message")

	ident: ClassVar[bytes]

	_message_classes = dict[bytes, "type[Message]"]()
	_hdr_struct = Struct("!lc")

	@classmethod
	def __init_subclass__(cls, /, ident: bytes = b""):
		super().__init_subclass__()
		if ident:  # pragma: no-branch
			assert len(ident) == 1
			Message._message_classes[ident] = cls
			cls.ident = ident

	@classmethod
	def unpack(cls, buf: FixedSizeBuffer) -> tuple[Message, int]:
		"""
		Unpack a message in buff and return a subclass instance and the number of bytes read
		"""
		hdr_size = cls._hdr_struct.size
		if buf.filled < hdr_size:
			raise NeedsMore
		size, ident = cls._hdr_struct.unpack_from(buf[:])
		assert isinstance(size, int)
		assert isinstance(ident, bytes)
		end = hdr_size + size - 1
		if buf.filled < end:
			raise NeedsMore
		try:
			msg_class = cls._message_classes[ident]
		except KeyError:
			raise NotImplementedError(buf[:end].tobytes())
		else:
			with buf[hdr_size:end] as data:
				return msg_class.from_buffer(data), end

	@classmethod
	@abstractmethod
	def from_buffer(cls: type[Self], buf: memoryview) -> Self:
		"""
		Construct an instance with values unpacked from a buffer

		Concrete classes must implement this method to unpack the values each class needs.
		The buffer view contains the message contents, from after the five byte header, up
		to the length indicated by the header.
		"""
		raise NotImplementedError  # pragma: no-cover

	def pack(self, buf: FixedSizeBuffer) -> None:
		"""
		Pack a message onto the end of a buffer
		"""
		cls = type(self)
		hdr_size = cls._hdr_struct.size
		buf_mark = buf.filled
		header = buf.get_free(hdr_size)
		try:
			self.to_buffer(buf)
		except InsufficientSpace:
			# revert buffer
			del buf[buf_mark:]
			raise
		size = buf.filled - buf_mark - LONG.size
		cls._hdr_struct.pack_into(header, 0, size, cls.ident)

	@abstractmethod
	def to_buffer(self, buf: FixedSizeBuffer) -> None:
		"""
		Pack a message's contents into a buffer

		Concrete classes must implement this method to pack the values each class needs.
		Implementations must not write the message header.
		"""
		raise NotImplementedError  # pragma: no-cover

	def release(self) -> None:
		"""
		Release any memoryviews a message holds of a buffer from which it was created

		Concrete classes MUST implement this if they store references to memoryviews, or any
		value that could be a memoryview.
		"""


class NoDataMessage(Message):
	"""
	Base class implementing `Message` abstract methods for messages with no contents
	"""

	if TYPE_CHECKING:
		Self = TypeVar("Self", bound="NoDataMessage")

	def __repr__(self) -> str:
		return f"{self.__class__.__name__}()"

	@classmethod
	def from_buffer(cls: type[Self], buf: memoryview) -> Self:
		assert len(buf) == 0, "message has some data"
		return cls()

	def to_buffer(self, buf: FixedSizeBuffer) -> None:
		return


class BytesMessage(Message):
	"""
	Base class implementing `Message` abstract methods for messages with unstructured contents
	"""

	if TYPE_CHECKING:
		Self = TypeVar("Self", bound="BytesMessage")

	content: memoryview

	def __init__(self, content: bytes):
		self.content = memoryview(content).toreadonly()

	def __repr__(self) -> str:
		content = repr(self.content.tobytes()) if len(self.content) <= 30 else \
			f"{self.content[:20].tobytes()!r} + {len(self.content)-20} further bytes"
		return f"{self.__class__.__name__}({content})"

	def __eq__(self, other: object) -> bool:
		if not isinstance(other, type(self)):
			return NotImplemented
		return other.content == self.content

	@classmethod
	def from_buffer(cls: type[Self], buf: memoryview) -> Self:
		return cls(buf)

	def to_buffer(self, buf: FixedSizeBuffer) -> None:
		buf[:] = self.content

	def release(self) -> None:
		self.content.release()


# MTA Setup Commands

@dataclass
class Negotiate(Message, ident=b"O"):
	"""
	Message type for MTA and filters to negotiate the features they provide and need

	A session starts with an MTA connecting to a filter and sending a negotiate message with
	the action and protocol flags it supports.  The filter then returns a negotiate message
	with the subset of the flags it wants to use, and optionally the macros (symbols) it
	wants before each stage.
	"""

	if TYPE_CHECKING:
		Self = TypeVar("Self", bound="Negotiate")

	version: int

	# TODO: use set[Enum]?
	action_flags: int
	protocol_flags: int

	macros: Mapping[Stage, Collection[str]] = field(default_factory=dict)

	_struct = Struct("!LLL")

	@classmethod
	def from_buffer(cls: type[Self], buf: memoryview) -> Self:
		opts = cast(tuple[int, int, int], cls._struct.unpack_from(buf))
		buf = buf[cls._struct.size:]
		macros = dict()
		while len(buf) > 0:
			stage, *_ = LONG.unpack_from(buf)
			names, buf = split_cstring(buf[LONG.size:])
			macros[Stage(stage)] = names.tobytes().decode("utf-8").split()
		return cls(*opts, macros)

	def to_buffer(self, buf: FixedSizeBuffer) -> None:
		self._struct.pack_into(
			buf.get_free(self._struct.size), 0,
			self.version, self.action_flags, self.protocol_flags,
		)
		join = " ".join
		for stage in Stage:
			try:
				names = join(self.macros[stage]).encode("utf-8")
			except KeyError:
				continue
			LONG.pack_into(buf.get_free(LONG.size), 0, stage.value)
			write_cstring(buf, names)


@dataclass
class Macro(Message, ident=b"D"):
	"""
	A message type for transferring symbol mappings prior to a stage event
	"""

	if TYPE_CHECKING:
		Self = TypeVar("Self", bound="Macro")

	stage: bytes
	macros: Mapping[str, str]

	_struct = Struct("!c")

	@classmethod
	def from_buffer(cls: type[Self], buf: memoryview) -> Self:
		stage, *_ = cls._struct.unpack_from(buf)
		macros = {}
		with buf[1:] as buf:
			while len(buf) > 0:
				key, buf = split_cstring(buf)
				val, buf = split_cstring(buf)
				macros[key.tobytes().decode("ascii")] = val.tobytes().decode("ascii")
		return cls(stage, macros)

	def to_buffer(self, buf: FixedSizeBuffer) -> None:
		self._struct.pack_into(buf.get_free(self._struct.size), 0, self.stage)
		for key, val in self.macros.items():
			write_cstring(buf, key.encode("ascii"))
			write_cstring(buf, val.encode("ascii"))


# Event Messages

@dataclass
class Connect(Message, ident=b"C"):
	"""
	An Event message reporting a client connecting to the MTA

	The message contains a hostname from doing a reverse DNS lookup, or "[<address>]" if
	that fails; an address for known network families; and a port for stream types which
	have ports.

	The type of an address value indicates the address family: `ipaddress.IPv4Address` or
	`ipaddress.IPv6Address` for INET and INET6 addresses, `pathlib.Path` for UNIX addresses,
	or `None` for connections for which there is no known address (e.g. stdin).
	"""

	if TYPE_CHECKING:
		Self = TypeVar("Self", bound="Connect")

	hostname: str
	address: IPv4Address|IPv6Address|Path|None = None
	port: int = 0

	_struct = Struct("!H")

	@classmethod
	def from_buffer(cls: type[Self], buf: memoryview) -> Self:
		_hostname, buf = split_cstring(buf)
		hostname = _hostname.tobytes().decode("idna")
		family, buf = Family(buf[0:1].tobytes()), buf[1:]
		if family == Family.UNKNOWN:
			return cls(hostname)
		port, *_ = cls._struct.unpack_from(buf)
		addr, buf = split_cstring(buf[cls._struct.size:])
		if family == Family.UNIX:
			return cls(hostname, Path(addr.tobytes().decode()))
		return cls(hostname, ip_address(addr.tobytes().decode()), port)

	def to_buffer(self, buf: FixedSizeBuffer, offset: int = 0) -> None:
		write_cstring(buf, self.hostname.encode("idna"))
		match self.address:
			case None:
				family = Family.UNKNOWN
			case Path():
				family = Family.UNIX
			case IPv4Address():
				family = Family.INET
			case IPv6Address():
				family = Family.INET6
			case _:  # pragma: no-cover
				if __debug__:  # type: ignore  # Unreachable
					raise TypeError(f"unknown address type: {type(self.address)}")
		buf[:] = family.value
		if family is Family.UNKNOWN:
			return
		self._struct.pack_into(buf.get_free(self._struct.size), 0, self.port)
		write_cstring(buf, str(self.address).encode())


@dataclass
class Helo(Message, ident=b"H"):
	"""
	An event message reporting a client sent an SMTP HELO/EHLO command
	"""

	if TYPE_CHECKING:
		Self = TypeVar("Self", bound="Helo")

	hostname: str

	@classmethod
	def from_buffer(cls: type[Self], buf: memoryview) -> Self:
		hostname, _ = split_cstring(buf)
		return cls(hostname.tobytes().decode("idna"))

	def to_buffer(self, buf: FixedSizeBuffer) -> None:
		write_cstring(buf, self.hostname.encode("idna"))


@dataclass
class EnvelopeFrom(Message, ident=b"M"):
	"""
	An event message reporting a client sent an SMTP "MAIL FROM" command
	"""

	if TYPE_CHECKING:
		Self = TypeVar("Self", bound="EnvelopeFrom")

	sender: bytes
	arguments: list[bytes] = field(default_factory=list)

	@classmethod
	def from_buffer(cls: type[Self], buf: memoryview) -> Self:
		args = cstring_iter(buf)
		return cls(next(args), [*args])

	def to_buffer(self, buf: FixedSizeBuffer) -> None:
		write_cstring(buf, self.sender)
		for arg in self.arguments:
			write_cstring(buf, arg)

	def release(self) -> None:
		if isinstance(self.sender, memoryview):
			self.sender.release()
		for arg in self.arguments:
			if isinstance(arg, memoryview):
				arg.release()


@dataclass
class EnvelopeRecipient(Message, ident=b"R"):
	"""
	An event message reporting a client sent an SMTP "RCPT TO" command

	A client must send at least one "RCPT TO" command, and can send multiple.
	"""

	if TYPE_CHECKING:
		Self = TypeVar("Self", bound="EnvelopeRecipient")

	recipient: bytes
	arguments: list[bytes] = field(default_factory=list)

	@classmethod
	def from_buffer(cls: type[Self], buf: memoryview) -> Self:
		args = cstring_iter(buf)
		return cls(next(args), [*args])

	def to_buffer(self, buf: FixedSizeBuffer) -> None:
		write_cstring(buf, self.recipient)
		for arg in self.arguments:
			write_cstring(buf, arg)

	def release(self) -> None:
		if isinstance(self.recipient, memoryview):
			self.recipient.release()
		for arg in self.arguments:
			if isinstance(arg, memoryview):
				arg.release()


class Data(NoDataMessage, ident=b"T"):
	"""
	An event message reporting a client sent an SMTP "DATA" command

	This event mainly indicates to a filter that there will be no further SMTP commands
	sent.
	"""


class Unknown(BytesMessage, ident=b"U"):
	"""
	An event message reporting a client sent an unknown SMTP command

	The raw command and arguments are sent as the message content.
	"""


@dataclass
class Header(Message, ident=b"L"):
	"""
	Transfers a header name and value from an email to a filter
	"""

	if TYPE_CHECKING:
		Self = TypeVar("Self", bound="Header")

	name: str
	value: bytes

	@classmethod
	def from_buffer(cls: type[Self], buf: memoryview) -> Self:
		name, buf = split_cstring(buf)
		value, buf = split_cstring(buf)
		assert len(buf) == 0
		return cls(name.tobytes().decode("ascii"), value)

	def to_buffer(self, buf: FixedSizeBuffer) -> None:
		write_cstring(buf, self.name.encode("ascii"))
		write_cstring(buf, self.value)

	def release(self) -> None:
		if isinstance(self.value, memoryview):
			self.value.release()


class EndOfHeaders(NoDataMessage, ident=b"N"):
	"""
	A message that indicates the end of an email's headers
	"""


class Body(BytesMessage, ident=b"B"):
	"""
	Transfers a chunk of an email body to a filter
	"""


class EndOfMessage(BytesMessage, ident=b"E"):
	"""
	A message that indicates the end of an email's body
	"""


class Abort(NoDataMessage, ident=b"A"):
	"""
	A notification that either the client or MTA decided to end a session before completion
	"""


class Close(NoDataMessage, ident=b"Q"):
	"""
	A notification of a session end, either after completion or an abort
	"""


# Event Responses

class Continue(NoDataMessage, ident=b"c"):
	"""
	A filter response instructing an MTA to continue without a specific decision
	"""


class Reject(NoDataMessage, ident=b"r"):
	"""
	A filter response instructing an MTA to reject a message
	"""


class Discard(NoDataMessage, ident=b"d"):
	"""
	A filter response instructing an MTA to reject a message without informing the client
	"""


class Accept(NoDataMessage, ident=b"a"):
	"""
	A filter response instructing an MTA to accept a message
	"""


class TemporaryFailure(NoDataMessage, ident=b"t"):
	"""
	A filter response instructing an MTA to reject a message temporarily (i.e. with a 4xx)
	"""


class Skip(NoDataMessage, ident=b"s"):
	"""
	A filter response instructing an MTA to skip the rest of a message's content

	This may only be sent in response to a Body message.
	"""


# TODO: This still needs implementing
class ReplyCode(BytesMessage, ident=b"y"):
	"""
	A filter response instructing an MTA to reject a message with a specific code and reason
	"""


# Modification Messages

@dataclass
class _AddrCmd(Message):
	"""
	Base class implementing `Message` abstract methods for messages with a single address
	"""

	if TYPE_CHECKING:
		Self = TypeVar("Self", bound="_AddrCmd")

	address: str

	@classmethod
	def from_buffer(cls: type[Self], buf: memoryview) -> Self:
		address, buf = split_cstring(buf)
		assert len(buf) == 0
		return cls(address.tobytes().decode("utf-8"))

	def to_buffer(self, buf: FixedSizeBuffer) -> None:
		write_cstring(buf, self.address.encode("utf-8"))


@dataclass
class _AddrParCmd(Message):
	"""
	Base class implementing `Message` abstract methods for messages with an address and arguments
	"""

	if TYPE_CHECKING:
		Self = TypeVar("Self", bound="_AddrParCmd")

	address: str
	args: str|None = None

	@classmethod
	def from_buffer(cls: type[Self], buf: memoryview) -> Self:
		args: memoryview|None = None
		address, buf = split_cstring(buf)
		if len(buf) > 0:
			args, buf = split_cstring(buf)
		assert len(buf) == 0
		return cls(
			address.tobytes().decode("utf-8"),
			None if args is None else args.tobytes().decode("utf-8"),
		)

	def to_buffer(self, buf: FixedSizeBuffer) -> None:
		write_cstring(buf, self.address.encode("utf-8"))
		if self.args:
			write_cstring(buf, self.args.encode("utf-8"))


class AddHeader(Header, ident=b"h"):
	"""
	Message from a filter to request a header is appended/prepended to the message

	TODO: Append or prepend?
	"""


@dataclass
class ChangeHeader(Message, ident=b"m"):
	"""
	Message from a filter to request a header is modified or removed at a given index
	"""

	if TYPE_CHECKING:
		Self = TypeVar("Self", bound="ChangeHeader")

	index: int
	name: str
	value: bytes

	@classmethod
	def from_buffer(cls: type[Self], buf: memoryview) -> Self:
		index, *_ = LONG.unpack_from(buf)
		name, buf = split_cstring(buf[LONG.size:])
		value, buf = split_cstring(buf)
		assert len(buf) == 0
		return cls(index, name.tobytes().decode("ascii"), value)

	def to_buffer(self, buf: FixedSizeBuffer) -> None:
		LONG.pack_into(buf.get_free(LONG.size), 0, self.index)
		write_cstring(buf, self.name.encode("ascii"))
		write_cstring(buf, self.value)

	def release(self) -> None:
		if isinstance(self.value, memoryview):
			self.value.release()


class InsertHeader(ChangeHeader, ident=b"i"):
	"""
	Message from a filter to request a header is inserted into the message
	"""


class ChangeSender(_AddrParCmd, ident=b"e"):
	"""
	Message from a filter to request the message sender is modified
	"""


class AddRecipient(_AddrCmd, ident=b"+"):
	"""
	Message from a filter to request a recipient is inserted into the envelope
	"""


class AddRecipientPar(_AddrParCmd, ident=b"2"):
	"""
	Message from a filter to request a recipient is inserted into the envelope, with parameters
	"""


class RemoveRecipient(_AddrCmd, ident=b"-"):
	"""
	Message from a filter to request a recipient is removed from the envelope
	"""


class ReplaceBody(BytesMessage, ident=b"b"):
	"""
	Message from a filter to request the wholesale replacement of the message body
	"""


class Progress(NoDataMessage, ident=b"p"):
	"""
	Message from a filter to inform an MTA that it is still operational, despite delays
	"""


@dataclass
class Quarantine(Message, ident=b"q"):
	"""
	Request that a message is quarantined (blocked, but kept for review)
	"""

	if TYPE_CHECKING:
		Self = TypeVar("Self", bound="Quarantine")

	reason: str

	@classmethod
	def from_buffer(cls: type[Self], buf: memoryview) -> Self:
		reason, buf = split_cstring(buf)
		assert len(buf) == 0
		return cls(reason.tobytes().decode("utf-8"))

	def to_buffer(self, buf: FixedSizeBuffer) -> None:
		write_cstring(buf, self.reason.encode("utf-8"))
