"""
Tests for FilterProtocol in core.py
"""

from __future__ import annotations

import unittest
from ipaddress import IPv4Address

from kilter.protocol.buffer import SimpleBuffer
from kilter.protocol.core import FilterProtocol
from kilter.protocol.core import Unimplemented
from kilter.protocol.exceptions import InvalidMessage
from kilter.protocol.exceptions import NeedsMore
from kilter.protocol.exceptions import UnexpectedMessage
from kilter.protocol.exceptions import UnimplementedWarning
from kilter.protocol.messages import NoDataMessage
from kilter.protocol.messages import *


class FilterProtocolTests(unittest.TestCase):
	"""
	Tests for the FilterProtocol class
	"""

	def test_simple_sequence(self) -> None:
		"""
		Check a simple, correct sequence of messages are transfered
		"""
		# Prepare input messages
		buf = SimpleBuffer(100)
		Negotiate(6, 0x1ff, 0xfffff).pack(buf)
		Macro(b"\x00", dict(spam="ham")).pack(buf)
		Connect("example.com", IPv4Address("10.1.1.1"), 11111).pack(buf)

		protocol = FilterProtocol()

		for msg in protocol.read_from(buf):
			match msg:
				case Negotiate():
					protocol.write_to(
						SimpleBuffer(20),
						Negotiate(6, 0x01, 0x11f),
					)
				case Connect():
					protocol.write_to(
						SimpleBuffer(20),
						Reject(),
					)

	def test_read_incomplete(self) -> None:
		"""
		Check that reading an incomplete message yields nothing
		"""
		buf = SimpleBuffer(20)
		buf[:] = b"\x00\x00\x00\x0d\xff\xff\xff"

		for _ in FilterProtocol().read_from(buf):
			self.fail("Incomplete message yielded")

	def test_read_unimplemented(self) -> None:
		"""
		Check that unknown messages cause a warning to be issued, and are yielded raw
		"""
		buf = SimpleBuffer(20)
		buf[:] = b"\x00\x00\x00\x01S"

		with self.assertWarns(UnimplementedWarning):
			for msg in FilterProtocol().read_from(buf):
				self.assertIsInstance(msg, Unimplemented)
				break
			else:
				self.fail("No messages read")

	def test_read_unexpected(self) -> None:
		"""
		Check that reading an available message before a response raises UnexpectedMessage
		"""
		# Prepare input messages
		buf = SimpleBuffer(100)
		Negotiate(6, 0x1ff, 0xfffff).pack(buf)
		Macro(b"\x00", dict(spam="ham")).pack(buf)
		Connect("example.com", IPv4Address("10.1.1.1"), 11111).pack(buf)

		with self.assertRaises(UnexpectedMessage):
			for _ in FilterProtocol().read_from(buf):
				pass

	def test_read_invalid_messages(self) -> None:
		"""
		Check that reading a known but invalid message raises InvalidMessage
		"""
		# Prepare input messages
		buf = SimpleBuffer(100)
		Skip().pack(buf)

		with self.assertRaises(InvalidMessage):
			for _ in FilterProtocol().read_from(buf):
				pass

	@unittest.expectedFailure
	def test_no_response(self) -> None:
		"""
		Check that a following message can be read immediately when no response is expected
		"""
		# Prepare input messages
		buf = SimpleBuffer(100)
		Negotiate(6, 0x1ff, 0xfffff).pack(buf)
		Connect("example.com", IPv4Address("10.1.1.1"), 11111).pack(buf)
		Helo("example.com").pack(buf)

		protocol = FilterProtocol()

		for msg in protocol.read_from(buf):
			match msg:
				case Negotiate():
					protocol.write_to(
						SimpleBuffer(20),
						Negotiate(6, 0x00, ProtocolFlags.NR_CONNECT),
					)
				case Connect():
					pass

	def test_write_unexpected_response(self) -> None:
		"""
		Check that writing a message when no response is expected raises UnexpectedMessage
		"""
		# Prepare input messages
		buf = SimpleBuffer(100)
		Negotiate(6, 0x1ff, 0xfffff).pack(buf)
		Connect("example.com", IPv4Address("10.1.1.1"), 11111).pack(buf)

		protocol = FilterProtocol()

		for msg in protocol.read_from(buf):
			match msg:
				case Negotiate():
					protocol.write_to(
						SimpleBuffer(20),
						Negotiate(6, 0x00, 0x00),
					)
				case Connect():
					protocol.write_to(
						SimpleBuffer(20),
						Continue(),
					)
					with self.assertRaises(UnexpectedMessage):
						protocol.write_to(
							SimpleBuffer(20),
							Continue(),
						)
					break
		else:
			self.fail("Connect not read")

	@unittest.expectedFailure
	def test_write_unexpected_response_nr(self) -> None:
		"""
		Check that writing a message when no response is expected raises UnexpectedMessage
		"""
		# Prepare input messages
		buf = SimpleBuffer(100)
		Negotiate(6, 0x1ff, 0xfffff).pack(buf)
		Connect("example.com", IPv4Address("10.1.1.1"), 11111).pack(buf)

		protocol = FilterProtocol()

		for msg in protocol.read_from(buf):
			match msg:
				case Negotiate():
					protocol.write_to(
						SimpleBuffer(20),
						Negotiate(6, 0x00, ProtocolFlags.NR_CONNECT),
					)
				case Connect():
					with self.assertRaises(UnexpectedMessage):
						protocol.write_to(
							SimpleBuffer(20),
							Continue(),
						)
					break
		else:
			self.fail("Connect not read")

	def test_write_unexpected_update(self) -> None:
		"""
		Check that writing an update when no update is expected raises UnexpectedMessage
		"""
		# Prepare input messages
		buf = SimpleBuffer(100)
		Negotiate(6, 0x1ff, 0xfffff).pack(buf)
		Connect("example.com", IPv4Address("10.1.1.1"), 11111).pack(buf)
		Helo("example.com").pack(buf)

		protocol = FilterProtocol()

		for msg in protocol.read_from(buf):
			match msg:
				case Negotiate():
					protocol.write_to(
						SimpleBuffer(20),
						Negotiate(6, ActionFlags.ADD_HEADERS, 0x00),
					)
				case Connect():
					with self.assertRaises(UnexpectedMessage):
						protocol.write_to(
							SimpleBuffer(20),
							AddHeader("test", b"spam"),
						)
					break
		else:
			self.fail("Connect not read")

	@unittest.expectedFailure
	def test_write_disallowed_update(self) -> None:
		"""
		Check that writing updates without negotiation raises UnexpectedMessage
		"""
		# Prepare input messages
		buf = SimpleBuffer(100)
		Negotiate(6, 0x1ff, 0xfffff).pack(buf)
		Connect("example.com", IPv4Address("10.1.1.1"), 11111).pack(buf)
		Helo("example.com").pack(buf)
		Data().pack(buf)
		EndOfHeaders().pack(buf)
		EndOfMessage(b"").pack(buf)

		protocol = FilterProtocol()

		for msg in protocol.read_from(buf):
			match msg:
				case Negotiate():
					protocol.write_to(
						SimpleBuffer(20),
						Negotiate(6, 0x00, 0x00),
					)
				case EndOfMessage():
					with self.assertRaises(UnexpectedMessage):
						protocol.write_to(
							SimpleBuffer(20),
							AddHeader("test", b"spam"),
						)
					break
				case _:
					protocol.write_to(
						SimpleBuffer(20),
						Continue(),
					)
		else:
			self.fail("EndOfMessage not read")

	def test_write_update(self) -> None:
		"""
		Check that writing an update message is accepted after an EOM message
		"""
		# Prepare input messages
		buf = SimpleBuffer(100)
		Negotiate(6, 0x1ff, 0xfffff).pack(buf)
		Connect("example.com", IPv4Address("10.1.1.1"), 11111).pack(buf)
		Helo("example.com").pack(buf)
		Data().pack(buf)
		EndOfHeaders().pack(buf)
		EndOfMessage(b"").pack(buf)

		protocol = FilterProtocol()

		for msg in protocol.read_from(buf):
			match msg:
				case Negotiate():
					protocol.write_to(
						SimpleBuffer(20),
						Negotiate(6, ActionFlags.ADD_HEADERS, 0x00),
					)
				case EndOfMessage():
					protocol.write_to(
						SimpleBuffer(20),
						AddHeader("test", b"spam"),
					)
					protocol.write_to(
						SimpleBuffer(20),
						AddHeader("x-test", b"ham"),
					)
				case _:
					protocol.write_to(
						SimpleBuffer(20),
						Continue(),
					)

	def test_write_invalid(self) -> None:
		"""
		Check that writing a response that is not valid for the event raises InvalidMessage
		"""
		# Prepare input messages
		buf = SimpleBuffer(100)
		Negotiate(6, 0x1ff, 0xfffff).pack(buf)
		Connect("example.com", IPv4Address("10.1.1.1"), 11111).pack(buf)

		protocol = FilterProtocol()

		for msg in protocol.read_from(buf):
			match msg:
				case Negotiate():
					protocol.write_to(
						SimpleBuffer(20),
						Negotiate(6, ActionFlags.ADD_HEADERS, 0x00),
					)
				case Connect():
					with self.assertRaises(InvalidMessage):
						protocol.write_to(
							SimpleBuffer(20),
							Skip(),
						)
					break
		else:
			self.fail("Connect not read")
