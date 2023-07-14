"""
Tests for classes in the kilter.protocol.messages module
"""

from __future__ import annotations

import abc
import struct
from ipaddress import IPv4Address
from ipaddress import IPv6Address
from pathlib import Path
from typing import Any
from typing import ClassVar
from typing import Iterator
from typing import Mapping
from typing import Protocol
from typing import Sequence
from typing import TypeVar
from typing import get_args as get_type_args
from typing import get_origin as get_type_origin
from unittest import TestCase

from kilter.protocol import messages
from kilter.protocol.buffer import SimpleBuffer
from kilter.protocol.exceptions import InsufficientSpace
from kilter.protocol.exceptions import NeedsMore
from kilter.protocol.exceptions import UnknownMessage

from .unittest_helpers import TestCaseMixin

IPV4_ADDR = IPv4Address("10.0.0.1")
IPV6_ADDR = IPv6Address("fd00::1")
UNIX_ADDR = Path("path/to.sock")

T = TypeVar("T", bound="messages.Message")

TestValues = tuple[
	Sequence[Any],                      # arguments
	Mapping[str, Any],                  # keyword arguments
	Mapping[str, Any],                  # attributes to check
	bytes,                              # example encoded message
]


def addr2cstring(addr: IPv4Address|IPv6Address) -> bytes:
	"""
	Convert an IP address into a NULL-terminated ASCII notation form
	"""
	return str(addr).encode("ascii") + b"\x00"


class MessageTests(TestCase):
	"""
	Tests for the base Message class which also acts as the parser
	"""

	def test_incomplete(self) -> None:
		"""
		Check that attempting to unpack incomplete messages raises NeedsMore
		"""
		buf = SimpleBuffer(50)

		buf[0:] = b"\x00\x00\x0f"
		with self.subTest("header"), self.assertRaises(NeedsMore):
			messages.Message.unpack(buf)

		buf[0:] = b"\x00\x00\x00\x0bCspam"
		with self.subTest("body"), self.assertRaises(NeedsMore):
			messages.Message.unpack(buf)

	def test_not_implemented(self) -> None:
		"""
		Check that attempting to unpack messages with unknown types raises UnknownMessage
		"""
		buf = SimpleBuffer(50)

		buf[0:] = b"\x00\x00\x00\x01Z"
		with self.assertRaises(UnknownMessage):
			messages.Message.unpack(buf)

	def test_malformatted(self) -> None:
		"""
		Check that attempting to unpack malformed packets raises ValueError
		"""
		buf = SimpleBuffer(50)

		buf[0:] = b"\x00\x00\x00\x05Cspam"
		with self.assertRaises(ValueError):
			messages.Message.unpack(buf)

	def test_no_space(self) -> None:
		"""
		Check that attempting to unpack to near-full buffer raises InsufficientSpace
		"""
		buf = SimpleBuffer(10)
		buf[:] = b"this is "
		message = messages.Body(b"an ex parrot")

		with self.assertRaises(InsufficientSpace):
			message.pack(buf)

			assert buf[:].tobytes() == b"this is "

	def test_no_space_after_header(self) -> None:
		"""
		Check that attempting to pack to near-full buffer raises InsufficientSpace

		Differs from `test_no_space` in that there is sufficient space for the message
		header.
		"""
		buf = SimpleBuffer(15)
		buf[:] = b"this is "
		message = messages.Body(b"an ex parrot")

		with self.assertRaises(InsufficientSpace):
			message.pack(buf)

			assert buf[:].tobytes() == b"this is "


class GenericTests(TestCaseMixin, Protocol[T]):
	"""
	Generic tests for all Message subclasses
	"""

	message_class: type[T]
	message_ident: ClassVar[bytes]
	holds_views: bool

	@classmethod
	def __init_subclass__(cls, *, ident: bytes = b"", holds_views: bool = True):
		cls.holds_views = holds_views
		if not ident:
			return
		cls.message_ident = ident
		base = cls
		for gbase in base.__orig_bases__:  # type: ignore
			if get_type_origin(gbase) is GenericTests:
				cls.message_class, *_ = get_type_args(gbase)
				return
		raise TypeError("need a concrete Message type subscript")

	@abc.abstractmethod
	def get_test_values(self) -> Iterator[TestValues]:
		"""
		Return class specific values for generic tests

		Implemented by Message subclass test cases to provided test values for the generic
		tests defined by this class.
		"""

	def test_init(self) -> None:
		"""
		Check that creating Message subclass instances works as expected
		"""
		for args, kwargs, attr, _ in self.get_test_values():
			bad_kwargs = {**kwargs, "menu": "spam spam spam"}
			bad_args = [*args, "spam", "spam", "spam"]

			with self.subTest("good args", args=args, kwargs=kwargs):
				m = self.message_class(*args, **kwargs)

				self.assertDictEqual(m.__dict__, attr)

			with (
				self.subTest("bad keyword args", args=args, kwargs=bad_kwargs),
				self.assertRaises(TypeError),
			):
				m = self.message_class(*args, **bad_kwargs)

			with (
				self.subTest("bad positional args", args=bad_args, kwargs=kwargs),
				self.assertRaises(TypeError),
			):
				m = self.message_class(*bad_args, **kwargs)

	def test_to_buffer(self) -> None:
		"""
		Check that a message's to_buffer() method works as expected

		Note that to_buffer() does not write the header {unsigned long length; char type;}
		"""
		buf = SimpleBuffer(100)
		for args, kwargs, _, example in self.get_test_values():
			m = self.message_class(*args, **kwargs)
			del buf[:]

			with self.subTest(args=args, kwargs=kwargs):
				m.to_buffer(buf)

				assert buf[:].tobytes() == example

	def test_from_buffer(self) -> None:
		"""
		Check that a message's from_buffer()method works as expected
		"""
		buf = SimpleBuffer(100)
		for args, kwargs, attr, example in self.get_test_values():
			buf[0:] = example

			with self.subTest(args=args, kwargs=kwargs):
				m = self.message_class.from_buffer(buf[:])

				self.assertDictEqual(m.__dict__, attr)

	def test_message_unpack(self) -> None:
		"""
		Check that unpacking a message works as expected
		"""
		buf = SimpleBuffer(100)
		for args, kwargs, attr, example in self.get_test_values():
			buf[0:] = struct.pack("!lc", len(example) + 1, self.message_ident)
			buf[:] = example

			with self.subTest(args=args, kwargs=kwargs):
				m, s = messages.Message.unpack(buf)

				assert isinstance(m, self.message_class)
				assert s == 5 + len(example)
				self.assertDictEqual(m.__dict__, attr)

	def test_message_pack(self) -> None:
		"""
		Check that packing a message works as expected
		"""
		buf = SimpleBuffer(100)
		for args, kwargs, _, example in self.get_test_values():
			del buf[:]
			with self.subTest(args=args, kwargs=kwargs):
				m = self.message_class(*args, **kwargs)

				m.pack(buf)

				assert buf[5:].tobytes() == example
				assert struct.unpack("!lc", buf[:5]) == (buf.filled - 4, self.message_ident)

	def test_buffer_release(self) -> None:
		"""
		Check that releasing a message that holds memoryviews works
		"""
		buf = SimpleBuffer(100)
		for args, kwargs, _, example in self.get_test_values():
			buf[0:] = struct.pack("!lc", len(example) + 1, self.message_ident)
			buf[:] = example
			buf[:] = b"spam"  # needed to make the deletion do a resize
			m, s = messages.Message.unpack(buf)

			with self.subTest(args=args, kwargs=kwargs):
				if self.holds_views:
					with self.assertRaises(BufferError):
						del buf[:5]
				else:
					del buf[:5]

				m.release()
				del buf[:s-5]

	def test_buffer_release_noop(self) -> None:
		"""
		Check that releasing a message that holds no memoryviews works
		"""
		for args, kwargs, *_ in self.get_test_values():
			m = self.message_class(*args, **kwargs)

			with self.subTest(args=args, kwargs=kwargs):
				m.release()


class GenericNoDataTest:
	"""
	A mixin for GenericTests to simplify test cases for classes with no contents
	"""

	def get_test_values(self) -> Iterator[TestValues]:
		"""
		Return empty test values for classes with no constructor arguments, fields, etc.
		"""
		yield (tuple(), dict(), dict(), b"")


class GenericBytesTest:
	"""
	A mixin for GenericTests to simplify test cases for classes with unstructured content
	"""

	def get_test_values(self) -> Iterator[TestValues]:
		"""
		Return values for a single message field "content" that is unstructured
		"""
		test_bytes = b"this is an ex parrot"
		yield ((test_bytes,), dict(), dict(content=test_bytes), test_bytes)
		yield (tuple(), dict(content=test_bytes), dict(content=test_bytes), test_bytes)


class NegotiateMessageTests(
	TestCase,
	GenericTests[messages.Negotiate], ident=b"O",
	holds_views=False,
):
	"""
	Tests for the Negotiate message class
	"""

	def get_test_values(self) -> Iterator[TestValues]:
		"""
		Return test values for generic message tests, appropriate for Negotiate
		"""
		macros = {
			messages.Stage.CONNECT: ["spam", "eggs"],
			messages.Stage.HELO: ["ham"],
		}
		yield (
			(6, 0xFFFF, 0xAAAAAA), dict(),
			dict(version=6, action_flags=0xFFFF, protocol_flags=0xAAAAAA, macros=dict()),
			b"\x00\x00\x00\x06\x00\x00\xff\xff\x00\xaa\xaa\xaa",
		)
		yield (
			tuple(), dict(version=6, action_flags=0xFFFF, protocol_flags=0xAAAAAA),
			dict(version=6, action_flags=0xFFFF, protocol_flags=0xAAAAAA, macros=dict()),
			b"\x00\x00\x00\x06\x00\x00\xff\xff\x00\xaa\xaa\xaa",
		)
		yield (
			(6, 0xABCDEF01, 0xAAAAAAAA, macros), dict(),
			dict(version=6, action_flags=0xABCDEF01, protocol_flags=0xAAAAAAAA, macros=macros),
			b"\x00\x00\x00\x06\xab\xcd\xef\x01\xaa\xaa\xaa\xaa\x00\x00\x00\x00spam eggs\x00\x00\x00\x00\x01ham\x00",
		)


class MacroMessageTests(
	TestCase,
	GenericTests[messages.Macro], ident=b"D",
	holds_views=False,
):
	"""
	Tests for the Macro message class
	"""

	def get_test_values(self) -> Iterator[TestValues]:
		"""
		Return test values for generic message tests, appropriate for Macro
		"""
		yield (
			(b"C", {}), dict(),
			dict(stage=b"C", macros=dict()),
			b"C",
		)
		yield (
			(b"H",), dict(macros=dict(spam="ham", eggs="green")),
			dict(stage=b"H", macros=dict(spam="ham", eggs="green")),
			b"Hspam\x00ham\x00eggs\x00green\x00",
		)
		yield (
			tuple(), dict(stage=b"M", macros=dict(spam="ham", eggs="green")),
			dict(stage=b"M", macros=dict(spam="ham", eggs="green")),
			b"Mspam\x00ham\x00eggs\x00green\x00",
		)


class ConnectMessageTests(
	TestCase,
	GenericTests[messages.Connect], ident=b"C",
	holds_views=False,
):
	"""
	Tests for the Connect message class
	"""

	def get_test_values(self) -> Iterator[TestValues]:
		"""
		Return test values for generic message tests, appropriate for Connect
		"""
		yield (
			("тест.example.com",), {},
			dict(hostname="тест.example.com", address=None, port=0),
			b"xn--e1aybc.example.com\x00" + b"U",
		)
		yield (
			("test.example.com", UNIX_ADDR), {},
			dict(hostname="test.example.com", address=UNIX_ADDR, port=0),
			b"test.example.com\x00" + b"L" + b"\x00\x00" + b"path/to.sock\x00",
		)
		yield (
			("test.example.com", UNIX_ADDR, 0), {},
			dict(hostname="test.example.com", address=UNIX_ADDR, port=0),
			b"test.example.com\x00" + b"L" + b"\x00\x00" + b"path/to.sock\x00",
		)
		yield (
			("test.example.com", IPV4_ADDR, 25), {},
			dict(hostname="test.example.com", address=IPV4_ADDR, port=25),
			b"test.example.com\x00" + b"4" + b"\x00\x19" + addr2cstring(IPV4_ADDR),
		)
		yield (
			("test.example.com", IPV6_ADDR, 25), {},
			dict(hostname="test.example.com", address=IPV6_ADDR, port=25),
			b"test.example.com\x00" + b"6" + b"\x00\x19" + addr2cstring(IPV6_ADDR),
		)
		yield (
			("test.example.com",), dict(address=IPV4_ADDR, port=25),
			dict(hostname="test.example.com", address=IPV4_ADDR, port=25),
			b"test.example.com\x00" + b"4" + b"\x00\x19" + addr2cstring(IPV4_ADDR),
		)
		yield (
			(), dict(hostname="test.example.com", address=IPV6_ADDR),
			dict(hostname="test.example.com", address=IPV6_ADDR, port=0),
			b"test.example.com\x00" + b"6" + b"\x00\x00" + addr2cstring(IPV6_ADDR),
		)


class HeloMessageTests(
	TestCase,
	GenericTests[messages.Helo], ident=b"H",
	holds_views=False,
):
	"""
	Tests for the Helo message class
	"""

	def get_test_values(self) -> Iterator[TestValues]:
		"""
		Return test values for generic message tests, appropriate for Helo
		"""
		yield (
			("тест.example.com",), {},
			dict(hostname="тест.example.com"),
			b"xn--e1aybc.example.com\x00",
		)
		yield (
			(), dict(hostname="test.example.com"),
			dict(hostname="test.example.com"),
			b"test.example.com\x00",
		)


class EnvelopeFromMessageTests(TestCase, GenericTests[messages.EnvelopeFrom], ident=b"M"):
	"""
	Tests for the EnvelopeFrom message class
	"""

	def get_test_values(self) -> Iterator[TestValues]:
		"""
		Return test values for generic message tests, appropriate for EnvelopeFrom
		"""
		yield (
			(b"Test Sender <sender@test.example.com>", []), {},
			dict(sender=b"Test Sender <sender@test.example.com>", arguments=[]),
			b"Test Sender <sender@test.example.com>\x00",
		)
		yield (
			(b"Test Sender <sender@test.example.com>", [b"spam", b"ham"]), {},
			dict(sender=b"Test Sender <sender@test.example.com>", arguments=[b"spam", b"ham"]),
			b"Test Sender <sender@test.example.com>\x00spam\x00ham\x00",
		)
		yield (
			(b"Test Sender <sender@test.example.com>",), dict(arguments=[b"spam", b"ham"]),
			dict(sender=b"Test Sender <sender@test.example.com>", arguments=[b"spam", b"ham"]),
			b"Test Sender <sender@test.example.com>\x00spam\x00ham\x00",
		)


class EnvelopeRecipientMessageTests(TestCase, GenericTests[messages.EnvelopeRecipient], ident=b"R"):
	"""
	Tests for the EnvelopeRecipient message class
	"""

	def get_test_values(self) -> Iterator[TestValues]:
		"""
		Return test values for generic message tests, appropriate for EnvelopeRecipient
		"""
		yield (
			(b"Test Recipient <recipient@test.example.com>", []), {},
			dict(recipient=b"Test Recipient <recipient@test.example.com>", arguments=[]),
			b"Test Recipient <recipient@test.example.com>\x00",
		)
		yield (
			(b"Test Recipient <recipient@test.example.com>", [b"spam", b"ham"]), {},
			dict(recipient=b"Test Recipient <recipient@test.example.com>", arguments=[b"spam", b"ham"]),
			b"Test Recipient <recipient@test.example.com>\x00spam\x00ham\x00",
		)


class DataMessageTests(
	TestCase,
	GenericNoDataTest,
	GenericTests[messages.Data], ident=b"T",
	holds_views=False,
):
	"""
	Tests for the Data message class
	"""


class UnknownMessageTests(
	TestCase,
	GenericBytesTest,
	GenericTests[messages.Unknown], ident=b"U",
):
	"""
	Tests for the Unknown message class
	"""


class HeaderMessageTests(TestCase, GenericTests[messages.Header], ident=b"L"):
	"""
	Tests for the Header message class
	"""

	def get_test_values(self) -> Iterator[TestValues]:
		"""
		Return test values for generic message tests, appropriate for Header
		"""
		yield (
			("spam", b"eggs"), dict(),
			dict(name="spam", value=b"eggs"),
			b"spam\x00eggs\x00",
		)
		yield (
			("spam",), dict(value=b"eggs"),
			dict(name="spam", value=b"eggs"),
			b"spam\x00eggs\x00",
		)
		yield (
			tuple(), dict(name="spam", value=b"eggs"),
			dict(name="spam", value=b"eggs"),
			b"spam\x00eggs\x00",
		)


class EndOfHeadersMessageTests(
	TestCase,
	GenericNoDataTest,
	GenericTests[messages.EndOfHeaders], ident=b"N",
	holds_views=False,
):
	"""
	Tests for the EndOfHeader message class
	"""


class BodyMessageTests(
	TestCase,
	GenericBytesTest,
	GenericTests[messages.Body], ident=b"B",
):
	"""
	Tests for the Body message class
	"""

	def test_equality(self) -> None:
		"""
		Check equality comparison against another Body
		"""
		assert messages.Body(b"spam") == messages.Body(b"spam")
		assert messages.Body(b"spam") != messages.Body(b"ham")
		assert messages.Body(b"spam") != 1


class EndOfMessageMessageTests(
	TestCase,
	GenericBytesTest,
	GenericTests[messages.EndOfMessage], ident=b"E",
):
	"""
	Tests for the EndOfMessage message class
	"""


class AbortMessageTests(
	TestCase,
	GenericNoDataTest,
	GenericTests[messages.Abort], ident=b"A",
	holds_views=False,
):
	"""
	Tests for the Abort message class
	"""


class CloseMessageTests(
	TestCase,
	GenericNoDataTest,
	GenericTests[messages.Close], ident=b"Q",
	holds_views=False,
):
	"""
	Tests for the Close message class
	"""


class ContinueMessageTests(
	TestCase,
	GenericNoDataTest,
	GenericTests[messages.Continue], ident=b"c",
	holds_views=False,
):
	"""
	Tests for the Continue message class
	"""


class RejectMessageTests(
	TestCase,
	GenericNoDataTest,
	GenericTests[messages.Reject], ident=b"r",
	holds_views=False,
):
	"""
	Tests for the Reject message class
	"""


class DiscardMessageTests(
	TestCase,
	GenericNoDataTest,
	GenericTests[messages.Discard], ident=b"d",
	holds_views=False,
):
	"""
	Tests for the Discard message class
	"""


class AcceptMessageTests(
	TestCase,
	GenericNoDataTest,
	GenericTests[messages.Accept], ident=b"a",
	holds_views=False,
):
	"""
	Tests for the Accept message class
	"""


class TemporaryFailureMessageTests(
	TestCase,
	GenericNoDataTest,
	GenericTests[messages.TemporaryFailure], ident=b"t",
	holds_views=False,
):
	"""
	Tests for the TemporaryFailure message class
	"""


class SkipMessageTests(
	TestCase,
	GenericNoDataTest,
	GenericTests[messages.Skip], ident=b"s",
	holds_views=False,
):
	"""
	Tests for the Skip message class
	"""


class AddHeaderMessageTests(TestCase, GenericTests[messages.AddHeader], ident=b"h"):
	"""
	Tests for the AddHeader message class
	"""

	def get_test_values(self) -> Iterator[TestValues]:
		"""
		Return test values for generic message tests, appropriate for AddHeader
		"""
		yield (
			("spam", b"eggs"), dict(),
			dict(name="spam", value=b"eggs"),
			b"spam\x00eggs\x00",
		)
		yield (
			("spam",), dict(value=b"eggs"),
			dict(name="spam", value=b"eggs"),
			b"spam\x00eggs\x00",
		)
		yield (
			tuple(), dict(name="spam", value=b"eggs"),
			dict(name="spam", value=b"eggs"),
			b"spam\x00eggs\x00",
		)


class ChangeHeaderMessageTests(TestCase, GenericTests[messages.ChangeHeader], ident=b"m"):
	"""
	Tests for the ChangeHeader message class
	"""

	def get_test_values(self) -> Iterator[TestValues]:
		"""
		Return test values for generic message tests, appropriate for ChangeHeader
		"""
		yield (
			(1, "spam", b"eggs"), dict(),
			dict(index=1, name="spam", value=b"eggs"),
			b"\x00\x00\x00\x01spam\x00eggs\x00",
		)
		yield (
			(1, "spam"), dict(value=b"eggs"),
			dict(index=1, name="spam", value=b"eggs"),
			b"\x00\x00\x00\x01spam\x00eggs\x00",
		)
		yield (
			(1,), dict(name="spam", value=b"eggs"),
			dict(index=1, name="spam", value=b"eggs"),
			b"\x00\x00\x00\x01spam\x00eggs\x00",
		)
		yield (
			tuple(), dict(index=1, name="spam", value=b"eggs"),
			dict(index=1, name="spam", value=b"eggs"),
			b"\x00\x00\x00\x01spam\x00eggs\x00",
		)


class InsertHeaderMessageTests(TestCase, GenericTests[messages.InsertHeader], ident=b"i"):
	"""
	Tests for the InsertHeader message class
	"""

	def get_test_values(self) -> Iterator[TestValues]:
		"""
		Return test values for generic message tests, appropriate for InsertHeader
		"""
		yield (
			(1, "spam", b"eggs"), dict(),
			dict(index=1, name="spam", value=b"eggs"),
			b"\x00\x00\x00\x01spam\x00eggs\x00",
		)
		yield (
			(1, "spam"), dict(value=b"eggs"),
			dict(index=1, name="spam", value=b"eggs"),
			b"\x00\x00\x00\x01spam\x00eggs\x00",
		)
		yield (
			(1,), dict(name="spam", value=b"eggs"),
			dict(index=1, name="spam", value=b"eggs"),
			b"\x00\x00\x00\x01spam\x00eggs\x00",
		)
		yield (
			tuple(), dict(index=1, name="spam", value=b"eggs"),
			dict(index=1, name="spam", value=b"eggs"),
			b"\x00\x00\x00\x01spam\x00eggs\x00",
		)


class ChangeSenderMessageTests(
	TestCase,
	GenericTests[messages.ChangeSender], ident=b"e",
	holds_views=False,
):
	"""
	Tests for the ChangeSender message class
	"""

	def get_test_values(self) -> Iterator[TestValues]:
		"""
		Return test values for generic message tests, appropriate for ChangeSender
		"""
		yield (
			("test@example.com",), dict(),
			dict(address="test@example.com", args=None),
			b"test@example.com\x00",
		)
		yield (
			tuple(), dict(address="test@example.com"),
			dict(address="test@example.com", args=None),
			b"test@example.com\x00",
		)
		yield (
			("test@example.com",), dict(args="ESMTP ARGS"),
			dict(address="test@example.com", args="ESMTP ARGS"),
			b"test@example.com\x00ESMTP ARGS\x00",
		)
		yield (
			("test@example.com", "ESMTP ARGS"), dict(),
			dict(address="test@example.com", args="ESMTP ARGS"),
			b"test@example.com\x00ESMTP ARGS\x00",
		)


class AddRecipientMessageTests(
	TestCase,
	GenericTests[messages.AddRecipient], ident=b"+",
	holds_views=False,
):
	"""
	Tests for the AddRecipient message class
	"""

	def get_test_values(self) -> Iterator[TestValues]:
		"""
		Return test values for generic message tests, appropriate for AddRecipient
		"""
		yield (
			("test@example.com",), dict(),
			dict(address="test@example.com"),
			b"test@example.com\x00",
		)
		yield (
			tuple(), dict(address="test@example.com"),
			dict(address="test@example.com"),
			b"test@example.com\x00",
		)


class AddRecipientParMessageTests(
	TestCase,
	GenericTests[messages.AddRecipientPar], ident=b"2",
	holds_views=False,
):
	"""
	Tests for the AddRecipientPar message class
	"""

	def get_test_values(self) -> Iterator[TestValues]:
		"""
		Return test values for generic message tests, appropriate for AddRecipientPar
		"""
		yield (
			("test@example.com",), dict(),
			dict(address="test@example.com", args=None),
			b"test@example.com\x00",
		)
		yield (
			tuple(), dict(address="test@example.com"),
			dict(address="test@example.com", args=None),
			b"test@example.com\x00",
		)
		yield (
			("test@example.com",), dict(args="ESMTP ARGS"),
			dict(address="test@example.com", args="ESMTP ARGS"),
			b"test@example.com\x00ESMTP ARGS\x00",
		)
		yield (
			("test@example.com", "ESMTP ARGS"), dict(),
			dict(address="test@example.com", args="ESMTP ARGS"),
			b"test@example.com\x00ESMTP ARGS\x00",
		)


class RemoveRecipientMessageTests(
	TestCase,
	GenericTests[messages.RemoveRecipient], ident=b"-",
	holds_views=False,
):
	"""
	Tests for the RemoveRecipient message class
	"""

	def get_test_values(self) -> Iterator[TestValues]:
		"""
		Return test values for generic message tests, appropriate for RemoveRecipient
		"""
		yield (
			("test@example.com",), dict(),
			dict(address="test@example.com"),
			b"test@example.com\x00",
		)
		yield (
			tuple(), dict(address="test@example.com"),
			dict(address="test@example.com"),
			b"test@example.com\x00",
		)


class ReplaceBodyMessageTests(
	TestCase,
	GenericBytesTest,
	GenericTests[messages.ReplaceBody], ident=b"b",
):
	"""
	Tests for the ReplaceBody message class
	"""


class ProgressMessageTests(
	TestCase,
	GenericNoDataTest,
	GenericTests[messages.Progress], ident=b"p",
	holds_views=False,
):
	"""
	Tests for the Progress message class
	"""


class QuarantineMessageTests(
	TestCase,
	GenericTests[messages.Quarantine], ident=b"q",
	holds_views=False,
):
	"""
	Tests for the Quarantine message class
	"""

	def get_test_values(self) -> Iterator[TestValues]:
		"""
		Return test values for generic message tests, appropriate for Quarantine
		"""
		test_msg = "this is an ex parrot"
		test_bytes = b"this is an ex parrot\x00"
		yield ((test_msg,), dict(), dict(reason=test_msg), test_bytes)
		yield (tuple(), dict(reason=test_msg), dict(reason=test_msg), test_bytes)
