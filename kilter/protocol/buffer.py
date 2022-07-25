# Copyright 2022 Dominik Sekotill <dom.sekotill@kodo.org.uk>
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

"""
Structural type for buffers used by this milter package, plus a simple implementation

This module provides an abstract buffer interface and a simple implementation with poor
delete performance.

`FixedSizeBuffer` is the abstract type for a buffer to be used with
`kilter.protocol.core.FilterProtocol` and the pack and unpack methods of
`kilter.protocol.messages.Message`.

`SimpleBuffer` is the initial concrete implementation.
"""

from __future__ import annotations

from typing import Protocol

from .exceptions import InsufficientSpace


class FixedSizeBuffer(Protocol):
	"""
	The interface that must be presented by a buffer implementation for protocols

	Implementations must provide an item accessor interface that accepts ONLY slices.
	Methods that "get" data from the buffer return memoryviews, which can be indexed as
	normal.  How empty (unspecified) slice-start and -end values are treated depends on
	the operation.

	Set:

		The slice start defaults to the first unset index (i.e. the value of `self.filled`),
		slice stop defaults to the start index plus the length of the data being written.
		The size of the slice MUST be the same shape (length) as the data being written.
		In practice the stop value will rarely be specified.

		>>> from kilter.protocol.buffer import SimpleBuffer
		>>> buff = SimpleBuffer(50)
		>>> buff[:] = b"spam & "
		>>> buff[:] = b"eggs"
		>>> data = buff[:].tobytes()
		>>> data
		b'spam & eggs'

		These are equivalent:

		>>> buff[:] = data
		>>> buff[buff.filled:buff.filled + len(data)] = data

		Wrong shape:

		>>> buff[0:5] = b"spam"
		Traceback (most recent call last):
			...
		ValueError: ...

		Insufficient space:

		>>> buff = SimpleBuffer(10)
		>>> buff[:] = b"spam and eggs"
		Traceback (most recent call last):
			...
		InsufficientSpace: ...

	Get:

		The slice start defaults to the start of the buffer, and the slice stop defaults to
		the last set index.  The length of the returned memoryview will therefore be equal
		to `self.filled`.

		>>> buff = SimpleBuffer(10)
		>>> buff[:] = b"spam"
		>>> buff.filled, buff.available
		(4, 6)

	Delete:

		The slice defaults are as for get slices.
	"""

	def __len__(self) -> int: ...
	def __setitem__(self, items: slice, data: bytes) -> None: ...
	def __getitem__(self, items: slice) -> memoryview: ...
	def __delitem__(self, items: slice) -> None: ...

	@property
	def filled(self) -> int:
		"""
		The amount of the buffer (in bytes) that has been filled
		"""  # noqa: D401

	@property
	def available(self) -> int:
		"""
		The amount of the buffer (in bytes) that is unfilled and available
		"""  # noqa: D401

	def get_free(self, size: int) -> memoryview:
		"""
		Return a writable memoryview of a portion of available buffer space

		Raises `kilter.protocol.exceptions.InsufficientSpace` if the requested amount of
		space is not available.
		"""


class SimpleBuffer:
	"""
	A simple implementation of `FixedSizeBuffer`

	This implementation has poor delete performance when deleting from the head.
	"""

	__slots__ = "buffer", "filled",

	def __init__(self, capacity: int):
		self.buffer = bytearray(capacity)
		self.filled = 0

	def __len__(self) -> int:
		return len(self.buffer)

	def __setitem__(self, items: slice, data: bytes) -> None:
		assert items.start is None or isinstance(items.start, int)
		assert items.stop is None or isinstance(items.stop, int)
		start = self.filled if items.start is None else items.start
		stop = start + len(data) if items.stop is None else items.stop
		if items.step and items.step != 1:
			raise ValueError("buffer __setitem__: slice must be contiguous")
		if start + len(data) > len(self.buffer):
			raise InsufficientSpace
		with memoryview(self.buffer) as view:
			view[start:stop] = data
		self.filled = stop

	def __getitem__(self, items: slice) -> memoryview:
		s, e, _ = items.indices(self.filled)
		return memoryview(self.buffer)[s:e]

	def __delitem__(self, items: slice) -> None:
		start, stop, step = items.indices(self.filled)
		if step != 1:
			raise ValueError("buffer __delitem__: slice must be contiguous")
		if stop == self.filled:
			# no need to remove anything, just mark as empty
			self.filled = start
			return
		del self.buffer[start:stop]
		missing = stop - start
		self.filled -= missing
		self.buffer[len(self.buffer):] = b"\x00" * missing

	@property
	def available(self) -> int:
		"""
		The amount of the buffer (in bytes) that is unfilled and available
		"""  # noqa: D401
		return len(self.buffer) - self.filled

	def get_free(self, size: int) -> memoryview:
		"""
		Return a writable memoryview of a portion of available buffer space

		Raises `kilter.protocol.exceptions.InsufficientSpace` if the requested amount of
		space is not available.
		"""
		if size > self.available:
			raise InsufficientSpace
		start = self.filled
		stop = self.filled = start + size
		return memoryview(self.buffer)[start:stop]
