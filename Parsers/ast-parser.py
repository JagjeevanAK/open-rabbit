from tree_sitter import Language, Parser
import tree_sitter_python as tspython
import tree_sitter_javascript as tsjavascript
import tree_sitter_typescript as tstypescript

# Load languages using the new API
PY_LANGUAGE = Language(tspython.language())
JS_LANGUAGE = Language(tsjavascript.language())
TS_LANGUAGE = Language(tstypescript.language_typescript())

# Make a parser for each
parsers = {
    "python": Parser(PY_LANGUAGE),
    "javascript": Parser(JS_LANGUAGE),
    "typescript": Parser(TS_LANGUAGE),
}

# Example: Parse Python code
code_snippet = b"""
def hello(name):
    print(f"Hello, {name}!")
"""

tree = parsers["python"].parse(code_snippet)
print(tree.root_node)  
