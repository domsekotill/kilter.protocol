from unittest import TestCase

from kilter.protocol.buffer import SimpleBuffer
from kilter.protocol.exceptions import InsufficientSpace


class SimpleBufferTests(TestCase):
	"""
	Tests for `kilter.protocol.buffer.SimpleBuffer`
	"""

	def test_init(self) -> None:
		"""
		Check that a buffer can be created with expected arguments
		"""
		b = SimpleBuffer(10)

		assert b.buffer == b"\x00" * 10
		assert len(b) == 10

	def test_set(self) -> None:
		"""
		Check that assigning to a correctly shaped buffer slice works
		"""
		b = SimpleBuffer(50)
		with self.subTest("b[0:20]"):
			b[0:20] = b"this is an ex parrot"

			assert b.buffer == b"this is an ex parrot" + b"\x00" * 30
			assert b.filled == 20
			assert len(b) == 50

		b = SimpleBuffer(50)
		with self.subTest("b[20:40]"):
			b[20:40] = b"this is an ex parrot"

			assert b.buffer == b"\x00" * 20 + b"this is an ex parrot" + b"\x00" * 10
			assert b.filled == 40
			assert len(b) == 50

		b = SimpleBuffer(50)
		with self.subTest("b[:20]"):
			b[:20] = b"this is an ex parrot"

			assert b.buffer == b"this is an ex parrot" + b"\x00" * 30
			assert b.filled == 20
			assert len(b) == 50

		b = SimpleBuffer(50)
		with self.subTest("b[10:]"):
			b[10:] = b"this is an ex parrot"

			assert b.buffer == b"\x00" * 10 + b"this is an ex parrot" + b"\x00" * 20
			assert b.filled == 30
			assert len(b) == 50

		b = SimpleBuffer(50)
		with self.subTest("b[:]"):
			b[:] = b"this is an ex parrot"

			assert b.buffer == b"this is an ex parrot" + b"\x00" * 30
			assert b.filled == 20
			assert len(b) == 50

		b = SimpleBuffer(50)
		with self.subTest("b[::1]"):
			b[::1] = b"this is an ex parrot"

			assert b.buffer == b"this is an ex parrot" + b"\x00" * 30
			assert b.filled == 20
			assert len(b) == 50

		b = SimpleBuffer(50)
		with self.subTest("b[::2]"), self.assertRaises(ValueError):
			b[::2] = b"this is an ex parrot"

	def test_set_wrong_shape(self) -> None:
		"""
		Check that assigning to a buffer slice that is the wrong shape fails
		"""
		b = SimpleBuffer(50)

		with self.subTest("too small"), self.assertRaises(ValueError):
			b[:10] = b"this is an ex parrot"

		with self.subTest("too large"), self.assertRaises(ValueError):
			b[10:40] = b"this is an ex parrot"

		assert len(b) == 50

	def test_set_too_large(self) -> None:
		"""
		Check that assigning a string that is larger than the available space fails
		"""
		b = SimpleBuffer(10)
		with self.subTest("b[:]"), self.assertRaises(InsufficientSpace):
			b[:] = b"this is an ex parrot"

		b = SimpleBuffer(10)
		with self.subTest("b[5:]"), self.assertRaises(InsufficientSpace):
			b[5:] = b"this is an ex parrot"

		b = SimpleBuffer(10)
		with self.subTest("b[5:25]"), self.assertRaises(InsufficientSpace):
			b[5:25] = b"this is an ex parrot"

	def test_append(self) -> None:
		"""
		Check that assignments to unspecified slices appends in free space on the buffer
		"""
		b = SimpleBuffer(50)
		b[:] = b"this is an "

		b[:] = b"ex parrot"

		assert b.buffer == b"this is an ex parrot" + b"\x00" * 30
		assert b.filled == 20
		assert len(b) == 50

	def test_get(self) -> None:
		"""
		Check that accessing a buffer slice works
		"""
		b = SimpleBuffer(50)
		b[:20] = b"this is an ex parrot"

		assert b[:].tobytes() == b"this is an ex parrot"

	def test_del(self) -> None:
		"""
		Check that deleting a buffer slice works

		Of particular note: the buffer remains the same size, only the contents are deleted.
		"""
		b = SimpleBuffer(50)
		b[:] = b"this is an ex parrot"
		with self.subTest("b[:]"):
			del b[:]

			assert b[:] == b""
			assert b.filled == 0
			assert len(b) == 50

		b = SimpleBuffer(50)
		b[:] = b"this is an ex parrot"
		with self.subTest("b[:11]"):
			del b[:11]

			assert b[:] == b"ex parrot"
			assert b.filled == 9
			assert len(b) == 50

		b = SimpleBuffer(50)
		b[:] = b"this is an ex parrot"
		with self.subTest("b[:11:2]"), self.assertRaises(ValueError):
			del b[:11:2]

	def test_get_free(self) -> None:
		"""
		Check that get_free() works correctly
		"""
		b = SimpleBuffer(10)
		with self.subTest("free space available"):
			m = b.get_free(5)

			assert len(m) == 5
			assert b[:] == b"\x00" * 5
			assert b.available == 5 and b.filled == 5

		b = SimpleBuffer(10)
		with self.subTest("space not available"), self.assertRaises(InsufficientSpace):
			b.get_free(11)
