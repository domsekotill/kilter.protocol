from __future__ import annotations

import builtins
import re
import sys
from collections.abc import Callable
from importlib import import_module
from inspect import get_annotations
from types import ModuleType
from typing import Literal as L
from typing import Union
from warnings import warn

from sphinx.application import Sphinx

ObjType = Union[
	L["module"], L["class"], L["exception"], L["function"],
	L["method"], L["attribute"], L["property"],
]


def setup(app: Sphinx) -> None:
	app.connect("autodoc-process-docstring", add_roles)


def add_roles(
	app: Sphinx, what: ObjType, name: str, obj: object, options: object, lines: list[str],
) -> None:
	"""
	Add Sphinx roles to strings delimited with "`" in docstrings

	Polluting docstrings with RestructuredText markup is forbidden, so this plugin marks-up
	python objects in backticks for cross linking.
	"""
	replacer = get_replacer(what, obj, name)
	regex = re.compile(r"(?<![^:])`(?P<name>[a-z0-9_.]+)(\(\))?`", re.I)
	lines[:] = (regex.sub(replacer, line) for line in lines)


def get_replacer(
	what: ObjType, doc_obj: object, doc_obj_name: str,
) -> Callable[[re.Match[str]], str]:
	module, cls = get_context(what, doc_obj)

	def get_type(match: re.Match[str]) -> str:
		"""
		Given a match for a dot-name, return the RST type
		"""
		name = match.group("name")
		try:
			obj, parent, name = dot_import(module, cls, name)
		except AttributeError:
			warn(f"ignoring {match.group(0)} in docstring of {doc_obj_name}")
			return match.group(0)
		if isinstance(obj, ModuleType):
			role = ":py:mod:"
		elif isinstance(obj, type):
			role = ":py:exc:" if issubclass(obj, BaseException) else ":py:class:"
		elif callable(obj):
			role = ":py:meth:" if isinstance(parent, type) else ":py:func:"
		elif isinstance(parent, ModuleType):
			role = ":py:const:" if name.isupper() else ":py:data:"
		elif isinstance(parent, type):
			role = ":py:attr:"
		else:
			role = ":py:obj:"
		return f"{role}`{name}`"

	return get_type


def get_context(what: ObjType, obj: object) -> tuple[ModuleType, type|None]:
	"""
	Given an object and its type, return the module it's in and a class if appropriate

	These values form the starting points for searching for names.
	"""
	match what:
		case "module":
			assert isinstance(obj, ModuleType)
			return obj, None
		case "attribute" | "property" | "method":
			assert hasattr(obj, "__class__"), f"{what} {obj} has no attribute '__class__'"
			return import_module(obj.__class__.__module__), obj.__class__
		case "class" | "exception":
			assert isinstance(obj, type), f"{what} {obj!r} is not a type?!"
			return import_module(obj.__module__), obj
		case "function":
			assert hasattr(obj, "__module__"), f"{what} {obj!r} has no attribute '__module__'"
			return import_module(obj.__module__), None
	raise TypeError(f"unknown value for 'what': {what}")


def dot_import(module: ModuleType, cls: type|None, name: str) -> tuple[object, object, str]:
	"""
	Given a dot-separated name, return an object, its parent, and an absolute name for it

	The search is started from the context returned by `get_context()`.
	"""
	labels = list(name.split("."))
	obj, parent, name = dot_import_first(module, cls, labels.pop(0))
	for label in labels:
		parent = obj
		match obj:
			case ModuleType():
				obj = dot_import_from(obj, label)
			case type():
				try:
					obj = getattr(obj, label)
				except AttributeError:
					assert isinstance(obj, type)  # come on mypy…
					annotations = get_annotations(obj)
					if label not in annotations:
						raise
					obj = annotations[label]
			case _:
				obj = getattr(obj, label)
	return obj, parent, ".".join([name] + labels)


def dot_import_first(module: ModuleType, cls: type|None, name: str) -> tuple[object, object, str]:
	"""
	Given a name, return an object, its parent, and its absolute dot-separated name

	The name is search first from builtins; then top-level packages and modules; then
	submodules of the context module; then attributes of the context modules; then
	attributes of the context class, or as a special case the context class itself if the
	name is "self".
	"""
	try:
		return getattr(builtins, name), None, name
	except AttributeError:
		pass
	try:
		return import_module(name), None, name
	except ModuleNotFoundError:
		pass
	try:
		return dot_import_from(module, name), module, f"{module.__name__}.{name}"
	except AttributeError:
		if cls is None:
			raise
		return (
			(cls, module, f"{module.__name__}.{cls.__name__}") if name == "self" else \
			(getattr(cls, name), cls, f"{module.__name__}.{cls.__name__}.{name}")
		)


def dot_import_from(module: ModuleType, name: str) -> object:
	"""
	Given a module and name, return a submodule or module attribute of that name
	"""
	try:
		return import_module("." + name, module.__name__)
	except ModuleNotFoundError:
		return getattr(module, name)
