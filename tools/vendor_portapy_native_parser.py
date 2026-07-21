"""Drive the native full-core parser build from PortaPy-owned sources."""
from __future__ import annotations

import portapy.parser as parser_package
from portapy.parser.lexer import Lexer
from portapy.parser.parser import Parser

from tools import vendor_full_core_native_parser as _vendor


def vendor_native_parser() -> tuple[int, int]:
    """Generate the private native parser from ``src/portapy/parser``.

    The namespacing implementation remains shared with the original transition
    probe, but its source package and validation parser are explicitly rebound
    to PortaPy. The asmpython package is therefore a compiler only, not the
    interpreter parser source.
    """
    _vendor.compiler_package = parser_package
    _vendor.MODULES = ("errors", "ast_nodes", "lexer", "parser")
    _vendor.HostLexer = Lexer
    _vendor.HostParser = Parser
    return _vendor.vendor_native_parser()


__all__ = ["vendor_native_parser"]
