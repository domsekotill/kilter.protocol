import abc
from collections.abc import Mapping
from typing import Any
from typing import ContextManager
from typing import Protocol
from typing import TypeVar
from unittest.case import _AssertRaisesContext

E = TypeVar("E", bound="BaseException")


class TestCaseMixin(Protocol):
	"""
	A helper mixin for creating generic `unittest.TestCase` mixins

	Generic `unittest.TestCase` mixins are useful for writing shared tests for a large
	number of subclasses.

	Note that this is incomplete; if generic `unittest.TestCase` mixins need other methods
	from `unittest.TestCase` add them here.
	"""

	@abc.abstractmethod
	def subTest(self, msg: str = ..., **k: Any) -> ContextManager[None]: ...

	@abc.abstractmethod
	def assertDictEqual(self, d1: Mapping[Any, object], d2: Mapping[Any, object], msg: Any = ...) -> None: ...

	@abc.abstractmethod
	def assertRaises(self, expected_exception: type[E]) -> _AssertRaisesContext[E]: ...
