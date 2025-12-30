"""Utility functions to extract focused insights from AST and Semantic artifacts.

These helpers provide focused analysis data for code review:
- AST: function declarations and complexity, variable declarations and usages,
  import/export statements, and control-flow keywords.
- Semantic: functions, classes, variables, imports, call graphs, and inheritance.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Optional, Set

from agent.parsers.semantic.semantic_builder import SemanticGraph, EdgeType


def _node_text(node: Any, source_code: Optional[bytes]) -> str:
    """Safely decode the text associated with a tree-sitter node."""
    if source_code is not None and hasattr(node, "start_byte") and hasattr(node, "end_byte"):
        try:
            return source_code[node.start_byte : node.end_byte].decode("utf-8", errors="replace")
        except Exception:
            pass
    raw = getattr(node, "text", None)
    if raw is None:
        return ""
    if isinstance(raw, bytes):
        return raw.decode("utf-8", errors="replace")
    return str(raw)


def _node_lines(node: Any) -> Dict[str, Optional[int]]:
    """Return 1-indexed start/end line information for a node."""
    start = getattr(node, "start_point", None)
    end = getattr(node, "end_point", None)
    return {
        "start_line": (start[0] + 1) if start else None,
        "end_line": (end[0] + 1) if end else None,
    }


def generate_ast_report(ast_tree: Any, source_code: Optional[bytes], language: str) -> Dict[str, Any]:
    """Extract focused AST insights for the requested language."""
    if ast_tree is None:
        return {}

    root = getattr(ast_tree, "root_node", ast_tree)
    if root is None:
        return {}

    function_nodes = {
        "python": {"function_definition", "lambda"},
        "javascript": {
            "function_declaration", "function", "method_definition",
            "arrow_function", "generator_function",
        },
        "typescript": {
            "function_declaration", "method_signature", "method_definition",
            "arrow_function", "generator_function",
        },
        "tsx": {
            "function_declaration", "method_definition",
            "arrow_function", "generator_function",
        },
    }

    control_flow_nodes = {
        "if_statement", "else_clause", "switch_statement", "case_clause",
        "default_clause", "while_statement", "for_statement", "for_in_statement",
        "for_of_statement", "do_statement", "try_statement", "with_statement",
        "break_statement", "continue_statement", "return_statement",
        "raise_statement", "throw_statement", "assert_statement", "match_statement",
    }

    declaration_parents = {
        "assignment", "augmented_assignment", "assignment_expression",
        "assignment_pattern", "variable_declarator", "lexical_declaration",
        "variable_declaration", "pair_pattern", "typed_parameter",
        "parameter", "required_parameter", "optional_parameter", "identifier",
    }

    import_nodes = {
        "python": {"import_statement", "import_from_statement"},
        "javascript": {"import_statement"},
        "typescript": {"import_statement"},
        "tsx": {"import_statement"},
    }

    export_nodes = {
        "python": set(),
        "javascript": {"export_statement", "export_clause", "export_assignment"},
        "typescript": {"export_statement", "export_clause", "export_assignment"},
        "tsx": {"export_statement", "export_clause", "export_assignment"},
    }

    reserved_keywords = {
        "def", "class", "if", "else", "for", "while", "return", "import",
        "from", "export", "switch", "case", "break", "continue", "try",
        "except", "finally", "with", "raise", "throw",
    }

    functions: List[Dict[str, Any]] = []
    variable_map: Dict[str, Dict[str, Set[int]]] = defaultdict(lambda: {"declarations": set(), "usages": set()})
    imports_exports: List[Dict[str, Any]] = []
    control_keywords: List[Dict[str, Any]] = []

    function_types = function_nodes.get(language, set())
    import_types = import_nodes.get(language, set())
    export_types = export_nodes.get(language, set())

    def collect_function_info(node: Any):
        name = "<anonymous>"
        parameters: List[str] = []
        
        for child in node.children:
            if child.type in {"identifier", "property_identifier", "field_identifier", "name"}:
                text = _node_text(child, source_code).strip()
                if text:
                    name = text
                    break
        
        param_nodes = {
            "python": {"parameters"},
            "javascript": {"formal_parameters", "identifier", "formal_parameter"},
            "typescript": {"formal_parameters", "type_identifier", "parameter"},
            "tsx": {"formal_parameters", "parameter"},
        }
        param_types = param_nodes.get(language, {"parameters"})

        def gather_param_names(param_node: Any) -> List[str]:
            local_names: List[str] = []
            queue = [param_node]
            while queue:
                current = queue.pop()
                if current.type in {"identifier", "pattern", "shorthand_property_identifier"}:
                    txt = _node_text(current, source_code).strip()
                    if txt and txt not in reserved_keywords:
                        local_names.append(txt)
                queue.extend(child for child in current.children if child.type != "comment")
            return local_names

        for child in node.children:
            if child.type in param_types:
                parameters.extend(gather_param_names(child))

        def count_complexity(subnode: Any, skip_types) -> int:
            count = 0
            stack = [subnode]
            while stack:
                current = stack.pop()
                if current is node:
                    stack.extend(child for child in current.children if child.type != "comment")
                    continue
                if current.type in skip_types:
                    continue
                if current.type in control_flow_nodes:
                    count += 1
                stack.extend(child for child in current.children if child.type != "comment")
            return count

        nested_skip = function_types if function_types else {node.type}
        complexity = 1 + count_complexity(node, nested_skip)
        line_info = _node_lines(node)
        
        functions.append({
            "name": name,
            "complexity": complexity,
            "parameters": parameters,
            "start_line": line_info["start_line"],
            "end_line": line_info["end_line"],
        })

    def handle_import_export(node: Any, kind: str):
        text = _node_text(node, source_code).strip()
        if not text:
            return
        line_info = _node_lines(node)
        imports_exports.append({
            "kind": kind,
            "statement": text,
            "start_line": line_info["start_line"],
            "end_line": line_info["end_line"],
        })

    def register_variable(name: str, category: str, node: Any):
        if not name or name in reserved_keywords:
            return
        line = getattr(node, "start_point", None)
        line_no = (line[0] + 1) if line else None
        if line_no is None:
            return
        variable_map[name][category].add(line_no)

    def traverse(node: Any):
        if node.type in function_types:
            collect_function_info(node)

        if node.type in control_flow_nodes:
            snippet = _node_text(node, source_code).strip()
            line_info = _node_lines(node)
            control_keywords.append({
                "keyword": node.type,
                "snippet": snippet,
                "start_line": line_info["start_line"],
                "end_line": line_info["end_line"],
            })

        if node.type in import_types:
            handle_import_export(node, "import")
        if node.type in export_types:
            handle_import_export(node, "export")

        if node.type == "identifier":
            parent = getattr(node, "parent", None)
            name = _node_text(node, source_code).strip()
            if parent is not None and parent.type in declaration_parents:
                meaningful_children = [child for child in parent.children if child.type != "comment"]
                if meaningful_children and meaningful_children[0] is node:
                    register_variable(name, "declarations", node)
                else:
                    register_variable(name, "usages", node)
            else:
                register_variable(name, "usages", node)

        for child in node.children:
            if child.type == "comment":
                continue
            traverse(child)

    traverse(root)

    variables = []
    for name, groups in variable_map.items():
        decls = sorted(groups["declarations"])
        uses = sorted(groups["usages"])
        if not decls and not uses:
            continue
        variables.append({"name": name, "declarations": decls, "usages": uses})

    functions.sort(key=lambda item: (item["start_line"] or 0, item["name"]))
    variables.sort(key=lambda item: item["name"])
    control_keywords.sort(key=lambda item: (item["start_line"] or 0, item["keyword"]))

    summary = {
        "function_count": len(functions),
        "variable_count": len(variables),
        "import_statement_count": sum(1 for stmt in imports_exports if stmt["kind"] == "import"),
        "export_statement_count": sum(1 for stmt in imports_exports if stmt["kind"] == "export"),
        "control_keyword_count": len(control_keywords),
    }

    return {
        "language": language,
        "summary": summary,
        "functions": functions,
        "variables": variables,
        "imports_exports": imports_exports,
        "control_flow_keywords": control_keywords,
    }


def generate_semantic_report(semantic: SemanticGraph) -> Dict[str, Any]:
    """Generate focused semantic graph report."""
    if semantic is None:
        return {}
    
    functions: List[Dict[str, Any]] = []
    classes: List[Dict[str, Any]] = []
    variables: List[Dict[str, Any]] = []
    imports: List[Dict[str, Any]] = []
    
    for node_id, node in semantic.nodes.items():
        node_data = {
            "id": node_id,
            "name": node.name,
            "scope": node.scope,
            "start_line": node.start_line,
            "end_line": node.end_line,
        }
        
        if node.node_type == "function":
            node_data["signature"] = node.signature
            node_data["parameters"] = node.parameters
            node_data["return_type"] = node.return_type
            node_data["complexity"] = node.complexity
            functions.append(node_data)
        elif node.node_type == "class":
            node_data["snippet"] = node.code_snippet[:100] if node.code_snippet else ""
            classes.append(node_data)
        elif node.node_type == "variable":
            node_data["snippet"] = node.code_snippet[:100] if node.code_snippet else ""
            variables.append(node_data)
        elif node.node_type == "import":
            node_data["statement"] = node.code_snippet
            imports.append(node_data)
    
    calls: List[Dict[str, Any]] = []
    inheritance: List[Dict[str, Any]] = []
    references: List[Dict[str, Any]] = []
    
    for edge in semantic.edges:
        source_node = semantic.nodes.get(edge.source_id)
        target_node = semantic.nodes.get(edge.target_id)
        
        if source_node is None or target_node is None:
            continue
        
        edge_data = {
            "source_id": edge.source_id,
            "source_name": source_node.name,
            "target_id": edge.target_id,
            "target_name": target_node.name,
        }
        
        if edge.edge_type == EdgeType.CALLS:
            calls.append(edge_data)
        elif edge.edge_type == EdgeType.INHERITS:
            edge_data["parent"] = target_node.name
            edge_data["child"] = source_node.name
            inheritance.append(edge_data)
        elif edge.edge_type == EdgeType.REFERENCES:
            references.append(edge_data)
    
    # Build call graph
    call_graph = semantic.get_call_graph()
    call_graph_data = []
    for caller_id, callees in call_graph.items():
        caller = semantic.nodes.get(caller_id)
        if caller:
            callee_names = [semantic.nodes[c].name for c in callees if c in semantic.nodes]
            call_graph_data.append({
                "caller": caller.name,
                "caller_id": caller_id,
                "calls": callee_names,
            })
    
    # Build inheritance hierarchy
    inheritance_hierarchy = semantic.get_inheritance_hierarchy()
    hierarchy_data = []
    for child_id, parent_ids in inheritance_hierarchy.items():
        child = semantic.nodes.get(child_id)
        if child:
            parent_names = [semantic.nodes[p].name for p in parent_ids if p in semantic.nodes]
            hierarchy_data.append({
                "class": child.name,
                "class_id": child_id,
                "inherits_from": parent_names,
            })
    
    # Sort all lists
    functions.sort(key=lambda x: (x.get("start_line") or 0, x["name"]))
    classes.sort(key=lambda x: (x.get("start_line") or 0, x["name"]))
    variables.sort(key=lambda x: x["name"])
    imports.sort(key=lambda x: (x.get("start_line") or 0, x["name"]))
    
    summary = {
        "total_nodes": len(semantic.nodes),
        "total_edges": len(semantic.edges),
        "function_count": len(functions),
        "class_count": len(classes),
        "variable_count": len(variables),
        "import_count": len(imports),
        "call_count": len(calls),
        "inheritance_count": len(inheritance),
    }
    
    return {
        "summary": summary,
        "functions": functions,
        "classes": classes,
        "variables": variables,
        "imports": imports,
        "call_graph": call_graph_data,
        "inheritance_hierarchy": hierarchy_data,
        "calls": calls,
        "inheritance_relationships": inheritance,
        "references": references,
    }
