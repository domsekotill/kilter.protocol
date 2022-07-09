"""
Parsers and state machines for the communications protocol used between the MTAs and filters

Users looking for something as simple to use as libmilter should take a look at
`kilter.service`.
"""

from typing import TYPE_CHECKING

from .core import FilterProtocol as FilterProtocol
from .exceptions import *
from .messages import *

if TYPE_CHECKING:
	from .buffer import FixedSizeBuffer as FixedSizeBuffer

__version__ = "0.1.3"
