"""
Tests for FilterProtocol in core.py
"""

from __future__ import annotations

import unittest
from ipaddress import IPv4Address
from warnings import catch_warnings

from kilter.protocol.buffer import SimpleBuffer
from kilter.protocol.core import FilterProtocol
from kilter.protocol.exceptions import InvalidMessage
from kilter.protocol.exceptions import NeedsMore
from kilter.protocol.exceptions import UnexpectedMessage
from kilter.protocol.exceptions import UnknownMessage
from kilter.protocol.messages import NoDataMessage
from kilter.protocol.messages import *

ALL_ACTION_FLAGS = ActionFlags(0x1ff)
ALL_PROTOCOL_FLAGS = ProtocolFlags(0xfffff)


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
		Negotiate(6, ALL_ACTION_FLAGS, ALL_PROTOCOL_FLAGS).pack(buf)
		Macro(0, dict(spam="ham")).pack(buf)
		Connect("example.com", IPv4Address("10.1.1.1"), 11111).pack(buf)

		protocol = FilterProtocol()

		for msg in protocol.read_from(buf):
			match msg:
				case Negotiate():
					protocol.write_to(
						SimpleBuffer(20),
						Negotiate(6, ActionFlags.ADD_HEADERS, ProtocolFlags(0x13e)),
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
		Check that unknown messages cause UnknownMessage to be raised
		"""
		buf = SimpleBuffer(20)
		buf[:] = msg = b"\x00\x00\x00\x01S"

		with self.assertRaises(UnknownMessage) as exc_cm:
			for _ in FilterProtocol().read_from(buf):
				break
			else:
				self.fail("No messages read")

		assert exc_cm.exception.contents == msg

	def test_read_unimplemented_abort(self) -> None:
		"""
		Check that unknown messages cause Abort to be returned when enabled
		"""
		buf = SimpleBuffer(20)
		buf[:] = b"\x00\x00\x00\x01S"

		for msg in FilterProtocol(abort_on_unknown=True).read_from(buf):
			assert isinstance(msg, Abort)
			break
		else:
			self.fail("No messages read")

	def test_read_unexpected(self) -> None:
		"""
		Check that reading an available message before a response raises UnexpectedMessage
		"""
		# Prepare input messages
		buf = SimpleBuffer(100)
		Negotiate(6, ALL_ACTION_FLAGS, ALL_PROTOCOL_FLAGS).pack(buf)
		Macro(0, dict(spam="ham")).pack(buf)
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

	def test_no_response(self) -> None:
		"""
		Check that a following message can be read immediately when no response is expected
		"""
		# Prepare input messages
		buf = SimpleBuffer(100)
		Negotiate(6, ALL_ACTION_FLAGS, ALL_PROTOCOL_FLAGS).pack(buf)
		Connect("example.com", IPv4Address("10.1.1.1"), 11111).pack(buf)
		Helo("example.com").pack(buf)

		protocol = FilterProtocol()

		for msg in protocol.read_from(buf):
			match msg:
				case Negotiate():
					protocol.write_to(
						SimpleBuffer(20),
						Negotiate(6, ActionFlags.NONE, ProtocolFlags.NR_CONNECT),
					)
				case Connect():
					pass

	def test_write_unexpected_response(self) -> None:
		"""
		Check that writing a message when no response is expected raises UnexpectedMessage
		"""
		# Prepare input messages
		buf = SimpleBuffer(100)
		Negotiate(6, ALL_ACTION_FLAGS, ALL_PROTOCOL_FLAGS).pack(buf)
		Connect("example.com", IPv4Address("10.1.1.1"), 11111).pack(buf)

		protocol = FilterProtocol()

		for msg in protocol.read_from(buf):
			match msg:
				case Negotiate():
					protocol.write_to(
						SimpleBuffer(20),
						Negotiate(6, ActionFlags.NONE, ProtocolFlags.NONE),
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

	def test_write_unexpected_response_nr(self) -> None:
		"""
		Check that writing a message when no response is expected raises UnexpectedMessage
		"""
		# Prepare input messages
		buf = SimpleBuffer(100)
		Negotiate(6, ALL_ACTION_FLAGS, ALL_PROTOCOL_FLAGS).pack(buf)
		Connect("example.com", IPv4Address("10.1.1.1"), 11111).pack(buf)

		protocol = FilterProtocol()

		for msg in protocol.read_from(buf):
			match msg:
				case Negotiate():
					protocol.write_to(
						SimpleBuffer(20),
						Negotiate(6, ActionFlags.NONE, ProtocolFlags.NR_CONNECT),
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
		Negotiate(6, ALL_ACTION_FLAGS, ALL_PROTOCOL_FLAGS).pack(buf)
		Connect("example.com", IPv4Address("10.1.1.1"), 11111).pack(buf)
		Helo("example.com").pack(buf)

		protocol = FilterProtocol()

		for msg in protocol.read_from(buf):
			match msg:
				case Negotiate():
					protocol.write_to(
						SimpleBuffer(20),
						Negotiate(6, ActionFlags.ADD_HEADERS, ProtocolFlags.NONE),
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

	def test_write_disallowed_update(self) -> None:
		"""
		Check that writing updates without negotiation raises UnexpectedMessage
		"""
		# Prepare input messages
		buf = SimpleBuffer(100)
		Negotiate(6, ALL_ACTION_FLAGS, ALL_PROTOCOL_FLAGS).pack(buf)
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
						Negotiate(6, ActionFlags.NONE, ProtocolFlags.NONE),
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
		Negotiate(6, ALL_ACTION_FLAGS, ALL_PROTOCOL_FLAGS).pack(buf)
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
						Negotiate(6, ActionFlags.ADD_HEADERS, ProtocolFlags.NONE),
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
		Negotiate(6, ALL_ACTION_FLAGS, ALL_PROTOCOL_FLAGS).pack(buf)
		Connect("example.com", IPv4Address("10.1.1.1"), 11111).pack(buf)

		protocol = FilterProtocol()

		for msg in protocol.read_from(buf):
			match msg:
				case Negotiate():
					protocol.write_to(
						SimpleBuffer(20),
						Negotiate(6, ActionFlags.ADD_HEADERS, ProtocolFlags.NONE),
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

	def test_disallowed_opts(self) -> None:
		"""
		Check that requesting protocol options not offered by the MTA results in ValueError
		"""
		# Prepare input messages
		buf = SimpleBuffer(20)
		Negotiate(6, ALL_ACTION_FLAGS, ProtocolFlags.MAX_DATA_SIZE_1M).pack(buf)

		protocol = FilterProtocol()
		next(protocol.read_from(buf))  # Prime the state machine

		with self.assertRaises(ValueError):
			protocol.write_to(
				SimpleBuffer(20),
				Negotiate(6, ActionFlags.NONE, ProtocolFlags.MAX_DATA_SIZE_256K),
			)

	def test_disallowed_actions(self) -> None:
		"""
		Check that requesting protocol actions not offered by the MTA results in ValueError
		"""
		# Prepare input messages
		buf = SimpleBuffer(20)
		Negotiate(6, ALL_ACTION_FLAGS & ~ActionFlags.CHANGE_BODY, ALL_PROTOCOL_FLAGS).pack(buf)

		protocol = FilterProtocol()
		next(protocol.read_from(buf))  # Prime the state machine

		with self.assertRaises(ValueError):
			protocol.write_to(
				SimpleBuffer(20),
				Negotiate(6, ActionFlags.CHANGE_BODY|ActionFlags.CHANGE_HEADERS, ProtocolFlags.NONE),
			)

	def test_unrequested_action(self) -> None:
		"""
		Check that sending an action that was not requested raises UnexpectedMessage
		"""
		# Prepare input messages
		buf = SimpleBuffer(60)
		Negotiate(6, ALL_ACTION_FLAGS, ALL_PROTOCOL_FLAGS).pack(buf)
		Connect("example.com", IPv4Address("10.1.1.1"), 11111).pack(buf)
		EndOfMessage(b"").pack(buf)

		protocol = FilterProtocol()

		for msg in protocol.read_from(buf):
			match msg:
				case Negotiate():
					protocol.write_to(
						SimpleBuffer(20),
						Negotiate(6, ActionFlags.NONE, ALL_PROTOCOL_FLAGS),
					)
				case EndOfMessage():
					with self.assertRaises(UnexpectedMessage):
						protocol.write_to(
							SimpleBuffer(20),
							ReplaceBody(b""),
						)

	def test_action(self) -> None:
		"""
		Check that sending an allowed modification action raised no issues
		"""
		# Prepare input messages
		buf = SimpleBuffer(60)
		Negotiate(6, ALL_ACTION_FLAGS, ALL_PROTOCOL_FLAGS).pack(buf)
		Connect("example.com", IPv4Address("10.1.1.1"), 11111).pack(buf)
		EndOfMessage(b"").pack(buf)

		protocol = FilterProtocol()

		for msg in protocol.read_from(buf):
			match msg:
				case Negotiate():
					protocol.write_to(
						SimpleBuffer(20),
						Negotiate(6, ALL_ACTION_FLAGS, ALL_PROTOCOL_FLAGS),
					)
				case EndOfMessage():
					with catch_warnings(record=True) as warn_cm:
						protocol.write_to(
							SimpleBuffer(20),
							ReplaceBody(b""),
						)
					assert len(warn_cm) == 0

	def test_action_bad(self) -> None:
		"""
		Check that sending a disallowed message after EOM raises UnexpectedMessage
		"""
		# Prepare input messages
		buf = SimpleBuffer(60)
		Negotiate(6, ALL_ACTION_FLAGS, ALL_PROTOCOL_FLAGS).pack(buf)
		Connect("example.com", IPv4Address("10.1.1.1"), 11111).pack(buf)
		EndOfMessage(b"").pack(buf)

		protocol = FilterProtocol()

		for msg in protocol.read_from(buf):
			match msg:
				case Negotiate():
					protocol.write_to(
						SimpleBuffer(20),
						Negotiate(6, ALL_ACTION_FLAGS, ALL_PROTOCOL_FLAGS),
					)
				case EndOfMessage():
					with self.assertRaises(UnexpectedMessage):
						protocol.write_to(
							SimpleBuffer(20),
							Skip(),
						)

	def test_setsymlist_implicit(self) -> None:
		"""
		Check that sending a mapping of symbol lists sets SETSYMLIST and issues a warning
		"""
		# Prepare input messages
		buf = SimpleBuffer(20)
		Negotiate(6, ALL_ACTION_FLAGS, ALL_PROTOCOL_FLAGS).pack(buf)

		protocol = FilterProtocol()
		next(protocol.read_from(buf))  # Prime the state machine

		with self.assertWarns(UserWarning):
			protocol.write_to(
				SimpleBuffer(40),
				Negotiate(6, ActionFlags.NONE, ALL_PROTOCOL_FLAGS, {Stage.CONNECT: {"spam"}}),
			)

	def test_setsymlist_disallowed(self) -> None:
		"""
		Check that sending symbol lists when not offered by an MTA raises ValueError
		"""
		# Prepare input messages
		buf = SimpleBuffer(20)
		Negotiate(6, ALL_ACTION_FLAGS & ~ActionFlags.SETSYMLIST, ALL_PROTOCOL_FLAGS).pack(buf)

		protocol = FilterProtocol()
		next(protocol.read_from(buf))  # Prime the state machine

		with self.assertRaises(ValueError):
			protocol.write_to(
				SimpleBuffer(40),
				Negotiate(6, ActionFlags.SETSYMLIST, ALL_PROTOCOL_FLAGS, {Stage.CONNECT: {"spam"}}),
			)

	def test_setsymlist_implicit_disallowed(self) -> None:
		"""
		Check that sending symbol lists when not offered by an MTA raises ValueError
		"""
		# Prepare input messages
		buf = SimpleBuffer(20)
		Negotiate(6, ALL_ACTION_FLAGS & ~ActionFlags.SETSYMLIST, ALL_PROTOCOL_FLAGS).pack(buf)

		protocol = FilterProtocol()
		next(protocol.read_from(buf))  # Prime the state machine

		with self.assertWarns(UserWarning), self.assertRaises(ValueError):
			protocol.write_to(
				SimpleBuffer(40),
				Negotiate(6, ActionFlags.NONE, ALL_PROTOCOL_FLAGS, {Stage.CONNECT: {"spam"}}),
			)

	def test_negotiated(self) -> None:
		"""
		Check that attributes expose the correct negotiated information
		"""
		protocol = negotiated_protocol(
			ActionFlags.ADD_HEADERS|ActionFlags.CHANGE_HEADERS,
			ProtocolFlags.SKIP|ProtocolFlags.NR_CONNECT|ProtocolFlags.NR_HELO,
		)

		assert protocol.skip is True
		assert AddHeader.ident in protocol.actions
		assert ChangeHeader.ident in protocol.actions
		assert InsertHeader.ident in protocol.actions
		self.assertSetEqual(protocol.nr, {Connect.ident, Helo.ident})

	def test_negotiated_none(self) -> None:
		"""
		Check that attributes expose the correct negotiated information
		"""
		protocol = negotiated_protocol(ActionFlags.NONE, ProtocolFlags.NONE)

		assert protocol.skip is False
		assert len(protocol.nr) == 0

	def test_needs_response(self) -> None:
		"""
		Check that needs_response returns True for selected messages
		"""
		protocol = negotiated_protocol(
			ActionFlags.NONE,
			ProtocolFlags.NR_CONNECT|ProtocolFlags.NR_HELO,
		)

		assert protocol.needs_response(Negotiate(0, ActionFlags.NONE, ProtocolFlags.NONE))
		assert not protocol.needs_response(Connect("example.com"))
		assert not protocol.needs_response(Helo("example.com"))
		assert not protocol.needs_response(Macro(0, {}))
		assert not protocol.needs_response(Abort())
		assert not protocol.needs_response(Close())
		assert protocol.needs_response(EnvelopeRecipient(b"spam@example.com"))
		assert protocol.needs_response(Data())

	def test_skip(self) -> None:
		"""
		Check that sending Skip when negotiated is allowed
		"""
		protocol = negotiated_protocol(ActionFlags.NONE, ProtocolFlags.SKIP)

		buf = SimpleBuffer(20)
		Body(b"spam").pack(buf)
		next(protocol.read_from(buf))

		protocol.write_to(SimpleBuffer(20), Skip())

	def test_skip_wrong_state(self) -> None:
		"""
		Check that sending Skip before one would be valid raises UnexpectedMessage
		"""
		protocol = negotiated_protocol(ActionFlags.NONE, ProtocolFlags.SKIP)

		with self.assertRaises(UnexpectedMessage):
			protocol.write_to(SimpleBuffer(20), Skip())

	def test_skip_not_negotiated(self) -> None:
		"""
		Check that sending Skip when not negotiated raises UnexpectedMessage
		"""
		protocol = negotiated_protocol(ActionFlags.NONE, ProtocolFlags.NONE)

		buf = SimpleBuffer(20)
		Body(b"spam").pack(buf)
		next(protocol.read_from(buf))

		with self.assertRaises(UnexpectedMessage):
			protocol.write_to(SimpleBuffer(20), Skip())


def negotiated_protocol(actions: ActionFlags, options: ProtocolFlags) -> FilterProtocol:
	"""
	Return a post-negotiation FilterProtocol which has negotiated for the given features
	"""
	buf = SimpleBuffer(20)
	Negotiate(6, ActionFlags.ALL, ALL_PROTOCOL_FLAGS).pack(buf)

	protocol = FilterProtocol()
	next(protocol.read_from(buf))  # Prime the state machine
	protocol.write_to(SimpleBuffer(20), Negotiate(6, actions, options))

	return protocol
