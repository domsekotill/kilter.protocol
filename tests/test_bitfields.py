"""
Tests for BitField classes in the kilter.protocol.messages module
"""

from __future__ import annotations

from unittest import TestCase

from kilter.protocol.messages import ActionFlags


class ActionFlagsTests(TestCase):
	"""
	Tests for packing and unpacking ActionFlags
	"""

	def test_pack(self) -> None:
		"""
		Check that packing a set of ActionFlag values into an int works
		"""
		flags = {ActionFlags.ADD_HEADERS, ActionFlags.CHANGE_BODY, ActionFlags.QUARANTINE}

		bitfield = ActionFlags.pack(flags)

		assert bitfield == 0x23

	def test_unpack(self) -> None:
		"""
		Check that unpacking a set of ActionFlags from an int works
		"""
		flags = ActionFlags.unpack(0x23)

		self.assertSetEqual(
			flags,
			{ActionFlags.ADD_HEADERS, ActionFlags.CHANGE_BODY, ActionFlags.QUARANTINE},
		)
