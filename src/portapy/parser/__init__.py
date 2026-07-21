"""PortaPy-owned indentation-aware lexer and recursive-descent parser."""
from .ast_nodes import Module
from .lexer import Lexer, Token
from .parser import Parser


def parse_source(source: str) -> Module:
    return Parser(Lexer(source).tokenize()).parse()


__all__ = ["Lexer", "Module", "Parser", "Token", "parse_source"]
