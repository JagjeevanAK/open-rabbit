"""
Semantic Graph Builder
Builds a semantic knowledge graph from AST, capturing code entities and their relationships
"""

from typing import Dict, List, Set, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum


class EdgeType(Enum):
    """Types of semantic relationships"""
    CALLS = "calls"                    # Function/method calls
    INHERITS = "inherits"              # Class inheritance
    IMPLEMENTS = "implements"          # Interface implementation
    IMPORTS = "imports"                # Module/package imports
    DEFINES = "defines"                # Variable/function definitions
    REFERENCES = "references"          # Variable/function references
    CONTAINS = "contains"              # Container relationships (class contains method)
    RETURNS = "returns"                # Function return type
    PARAMETER = "parameter"            # Function parameter type
    THROWS = "throws"                  # Exception throwing
    TYPE_OF = "type_of"               # Type information
    DECORATES = "decorates"           # Decorator application
    EXPORTS = "exports"               # Module exports


@dataclass
class SemanticNode:
    """Node in the semantic graph representing a code entity"""
    id: int
    name: str
    node_type: str  # function, class, variable, module, import, etc.
    scope: str = "global"
    
    # Source location
    start_line: Optional[int] = None
    end_line: Optional[int] = None
    file_path: Optional[str] = None
    
    # Semantic properties
    signature: Optional[str] = None  # Function/method signature
    return_type: Optional[str] = None
    parameters: List[str] = field(default_factory=list)
    modifiers: List[str] = field(default_factory=list)  # public, private, static, async, etc.
    docstring: Optional[str] = None
    
    # AST reference
    ast_node: Any = None
    
    # Metadata
    complexity: Optional[int] = None
    code_snippet: str = ""
    
    def to_dict(self) -> Dict:
        """Convert to dictionary representation"""
        return {
            "id": self.id,
            "name": self.name,
            "type": self.node_type,
            "scope": self.scope,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "signature": self.signature,
            "return_type": self.return_type,
            "parameters": self.parameters,
            "modifiers": self.modifiers,
            "docstring": self.docstring[:200] if self.docstring else None,
            "complexity": self.complexity,
            "code_snippet": self.code_snippet[:200] if self.code_snippet else ""
        }


@dataclass
class SemanticEdge:
    """Edge representing a semantic relationship between entities"""
    source_id: int
    target_id: int
    edge_type: EdgeType
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary representation"""
        return {
            "source": self.source_id,
            "target": self.target_id,
            "type": self.edge_type.value,
            "metadata": self.metadata
        }


class SemanticGraph:
    """Semantic Knowledge Graph for source code"""
    
    def __init__(self, name: str = "main"):
        self.name = name
        self.nodes: Dict[int, SemanticNode] = {}
        self.edges: List[SemanticEdge] = []
        self.next_node_id = 0
        
        # Indexes for fast lookup
        self.name_to_nodes: Dict[str, List[int]] = {}  # Name -> node IDs
        self.type_to_nodes: Dict[str, List[int]] = {}  # Type -> node IDs
        self.scope_hierarchy: Dict[str, List[str]] = {}  # Scope -> child scopes
        
    def create_node(
        self, 
        name: str, 
        node_type: str, 
        scope: str = "global"
    ) -> SemanticNode:
        """Create a new semantic node"""
        node = SemanticNode(
            id=self.next_node_id,
            name=name,
            node_type=node_type,
            scope=scope
        )
        self.nodes[self.next_node_id] = node
        self.next_node_id += 1
        
        # Update indexes
        if name not in self.name_to_nodes:
            self.name_to_nodes[name] = []
        self.name_to_nodes[name].append(node.id)
        
        if node_type not in self.type_to_nodes:
            self.type_to_nodes[node_type] = []
        self.type_to_nodes[node_type].append(node.id)
        
        return node
    
    def add_edge(
        self, 
        source_id: int, 
        target_id: int, 
        edge_type: EdgeType,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Add a semantic edge"""
        if source_id in self.nodes and target_id in self.nodes:
            edge = SemanticEdge(
                source_id=source_id,
                target_id=target_id,
                edge_type=edge_type,
                metadata=metadata or {}
            )
            self.edges.append(edge)
    
    def find_nodes_by_name(self, name: str) -> List[SemanticNode]:
        """Find all nodes with a given name"""
        node_ids = self.name_to_nodes.get(name, [])
        return [self.nodes[nid] for nid in node_ids]
    
    def find_nodes_by_type(self, node_type: str) -> List[SemanticNode]:
        """Find all nodes of a given type"""
        node_ids = self.type_to_nodes.get(node_type, [])
        return [self.nodes[nid] for nid in node_ids]
    
    def get_outgoing_edges(self, node_id: int, edge_type: Optional[EdgeType] = None) -> List[SemanticEdge]:
        """Get all outgoing edges from a node"""
        edges = [e for e in self.edges if e.source_id == node_id]
        if edge_type:
            edges = [e for e in edges if e.edge_type == edge_type]
        return edges
    
    def get_incoming_edges(self, node_id: int, edge_type: Optional[EdgeType] = None) -> List[SemanticEdge]:
        """Get all incoming edges to a node"""
        edges = [e for e in self.edges if e.target_id == node_id]
        if edge_type:
            edges = [e for e in edges if e.edge_type == edge_type]
        return edges
    
    def get_call_graph(self) -> Dict[int, List[int]]:
        """Build call graph: function -> functions it calls"""
        call_graph: Dict[int, List[int]] = {}
        for edge in self.edges:
            if edge.edge_type == EdgeType.CALLS:
                if edge.source_id not in call_graph:
                    call_graph[edge.source_id] = []
                call_graph[edge.source_id].append(edge.target_id)
        return call_graph
    
    def get_inheritance_hierarchy(self) -> Dict[int, List[int]]:
        """Build inheritance hierarchy: class -> parent classes"""
        hierarchy: Dict[int, List[int]] = {}
        for edge in self.edges:
            if edge.edge_type == EdgeType.INHERITS:
                if edge.source_id not in hierarchy:
                    hierarchy[edge.source_id] = []
                hierarchy[edge.source_id].append(edge.target_id)
        return hierarchy
    
    def to_dict(self) -> Dict:
        """Convert to dictionary representation"""
        return {
            "name": self.name,
            "nodes": {nid: node.to_dict() for nid, node in self.nodes.items()},
            "edges": [edge.to_dict() for edge in self.edges],
            "statistics": {
                "total_nodes": len(self.nodes),
                "total_edges": len(self.edges),
                "functions": len(self.find_nodes_by_type("function")),
                "classes": len(self.find_nodes_by_type("class")),
                "variables": len(self.find_nodes_by_type("variable")),
                "imports": len(self.find_nodes_by_type("import"))
            }
        }
    
    def to_dot(self) -> str:
        """Generate DOT format for visualization"""
        dot = [f'digraph "{self.name}_Semantic" {{']
        dot.append('  rankdir=LR;')
        dot.append('  node [shape=box, style=rounded];')
        
        # Define colors for different node types
        colors = {
            "function": "lightblue",
            "class": "lightgreen",
            "variable": "lightyellow",
            "import": "lightgray",
            "module": "lightcoral"
        }
        
        # Add nodes
        for node_id, node in self.nodes.items():
            color = colors.get(node.node_type, "white")
            label = f"{node.name}\\n({node.node_type})"
            if node.signature:
                label += f"\\n{node.signature[:30]}"
            
            dot.append(f'  {node_id} [label="{label}", fillcolor={color}, style="filled,rounded"];')
        
        # Add edges with different styles per type
        edge_styles = {
            EdgeType.CALLS: "solid,blue",
            EdgeType.INHERITS: "solid,green",
            EdgeType.IMPORTS: "dashed,gray",
            EdgeType.DEFINES: "solid,black",
            EdgeType.REFERENCES: "dotted,black",
            EdgeType.CONTAINS: "solid,purple"
        }
        
        for edge in self.edges:
            style = edge_styles.get(edge.edge_type, "solid,black")
            label = edge.edge_type.value
            dot.append(f'  {edge.source_id} -> {edge.target_id} [label="{label}", style="{style}"];')
        
        dot.append('}')
        return '\n'.join(dot)


class SemanticGraphBuilder:
    """Builds semantic graph from AST"""
    
    def __init__(self, language: str = "python"):
        self.language = language
        self.graph: Optional[SemanticGraph] = None
        self.source_code: Optional[bytes] = None
        self.current_scope: str = "global"
        self.scope_stack: List[str] = ["global"]
        
        # Tracking for relationship building
        self.function_nodes: Dict[str, int] = {}  # function name -> node id
        self.class_nodes: Dict[str, int] = {}     # class name -> node id
        self.variable_nodes: Dict[str, int] = {}  # variable name -> node id
        
    def build(self, ast_root, source_code: Optional[bytes] = None) -> SemanticGraph:
        """Build semantic graph from AST"""
        if source_code:
            self.source_code = source_code
        elif hasattr(ast_root, 'text'):
            self.source_code = ast_root.text
        
        self.graph = SemanticGraph(name="main")
        
        # Process the AST
        self._process_node(ast_root)
        
        return self.graph
    
    def _extract_text(self, node) -> str:
        """Extract text from AST node"""
        try:
            if hasattr(node, 'text'):
                return node.text.decode('utf-8', errors='replace')
        except Exception:
            pass
        return ""
    
    def _extract_snippet(self, node, max_length: int = 200) -> str:
        """Extract code snippet from AST node"""
        text = self._extract_text(node)
        text = ' '.join(text.split())
        if len(text) > max_length:
            return text[:max_length - 3] + "..."
        return text
    
    def _get_line_info(self, node) -> Tuple[Optional[int], Optional[int]]:
        """Get start and end line numbers"""
        start_line = None
        end_line = None
        if hasattr(node, 'start_point') and hasattr(node, 'end_point'):
            start_line = node.start_point[0] + 1
            end_line = node.end_point[0] + 1
        return start_line, end_line
    
    def _enter_scope(self, scope_name: str):
        """Enter a new scope"""
        parent_scope = self.current_scope
        self.current_scope = f"{parent_scope}.{scope_name}" if parent_scope != "global" else scope_name
        self.scope_stack.append(self.current_scope)
    
    def _exit_scope(self):
        """Exit current scope"""
        if len(self.scope_stack) > 1:
            self.scope_stack.pop()
            self.current_scope = self.scope_stack[-1]
    
    def _process_node(self, node):
        """Process AST node and extract semantic information"""
        if not node or not self.graph:
            return
        
        node_type = node.type
        
        # Process different node types
        if node_type in ['function_definition', 'function_declaration', 'method_definition',
                        'arrow_function', 'function', 'function_expression']:
            self._process_function(node)
        
        elif node_type in ['class_definition', 'class_declaration']:
            self._process_class(node)
        
        elif node_type in ['import_statement', 'import_from_statement']:
            self._process_import(node)
        
        elif node_type in ['export_statement']:
            self._process_export(node)
        
        elif node_type in ['call_expression', 'call']:
            self._process_call(node)
        
        elif node_type in ['assignment', 'variable_declaration', 'lexical_declaration']:
            self._process_variable(node)
        
        elif node_type in ['decorator']:
            self._process_decorator(node)
        
        # Recursively process children
        for child in node.children:
            self._process_node(child)
    
    def _process_function(self, node):
        """Process function/method definition"""
        if not self.graph:
            return
            
        # Extract function name
        func_name = "anonymous"
        for child in node.children:
            if child.type in ['identifier', 'property_identifier', 'name']:
                func_name = self._extract_text(child).strip()
                break
        
        # Create semantic node
        semantic_node = self.graph.create_node(
            name=func_name,
            node_type="function",
            scope=self.current_scope
        )
        
        # Set line info
        start_line, end_line = self._get_line_info(node)
        semantic_node.start_line = start_line
        semantic_node.end_line = end_line
        semantic_node.code_snippet = self._extract_snippet(node)
        semantic_node.ast_node = node
        
        # Extract parameters
        parameters = []
        return_type = None
        
        for child in node.children:
            if child.type in ['parameters', 'formal_parameters']:
                parameters = self._extract_parameters(child)
            elif child.type in ['type', 'type_annotation']:
                return_type = self._extract_text(child).strip()
        
        semantic_node.parameters = parameters
        semantic_node.return_type = return_type
        
        # Build signature
        param_str = ", ".join(parameters)
        signature = f"{func_name}({param_str})"
        if return_type:
            signature += f" -> {return_type}"
        semantic_node.signature = signature
        
        # Track for later relationship building
        self.function_nodes[func_name] = semantic_node.id
        
        # Enter function scope and process body
        self._enter_scope(func_name)
        
        # Process function body
        for child in node.children:
            if child.type in ['block', 'body', 'suite']:
                self._process_node(child)
        
        self._exit_scope()
    
    def _process_class(self, node):
        """Process class definition"""
        if not self.graph:
            return
            
        # Extract class name
        class_name = "AnonymousClass"
        for child in node.children:
            if child.type in ['identifier', 'type_identifier', 'name']:
                class_name = self._extract_text(child).strip()
                break
        
        # Create semantic node
        semantic_node = self.graph.create_node(
            name=class_name,
            node_type="class",
            scope=self.current_scope
        )
        
        start_line, end_line = self._get_line_info(node)
        semantic_node.start_line = start_line
        semantic_node.end_line = end_line
        semantic_node.code_snippet = self._extract_snippet(node)
        semantic_node.ast_node = node
        
        # Track class
        self.class_nodes[class_name] = semantic_node.id
        
        # Extract base classes (inheritance)
        for child in node.children:
            if child.type in ['argument_list', 'superclass', 'extends_clause', 'heritage_clause']:
                self._extract_inheritance(child, semantic_node.id)
        
        # Enter class scope and process body
        self._enter_scope(class_name)
        
        for child in node.children:
            if child.type in ['block', 'class_body', 'declaration_list']:
                self._process_node(child)
        
        self._exit_scope()
    
    def _process_import(self, node):
        """Process import statement"""
        if not self.graph:
            return
            
        import_text = self._extract_text(node).strip()
        
        # Create import node
        semantic_node = self.graph.create_node(
            name=import_text,
            node_type="import",
            scope=self.current_scope
        )
        
        start_line, end_line = self._get_line_info(node)
        semantic_node.start_line = start_line
        semantic_node.end_line = end_line
        semantic_node.code_snippet = import_text
        semantic_node.ast_node = node
    
    def _process_export(self, node):
        """Process export statement"""
        if not self.graph:
            return
            
        export_text = self._extract_text(node).strip()
        
        # Create export node
        semantic_node = self.graph.create_node(
            name=export_text,
            node_type="export",
            scope=self.current_scope
        )
        
        start_line, end_line = self._get_line_info(node)
        semantic_node.start_line = start_line
        semantic_node.end_line = end_line
        semantic_node.code_snippet = export_text
        semantic_node.ast_node = node
    
    def _process_call(self, node):
        """Process function call"""
        if not self.graph:
            return
            
        # Extract called function name
        callee_name = None
        for child in node.children:
            if child.type in ['identifier', 'attribute', 'member_expression']:
                callee_name = self._extract_text(child).strip()
                break
        
        if not callee_name:
            return
        
        # Find if this is a known function
        if callee_name in self.function_nodes:
            # Create CALLS edge from current scope to called function
            # We need to find the current function context
            # This is simplified - in production, maintain call context stack
            target_id = self.function_nodes[callee_name]
            
            # For now, we'll create a call reference node
            call_node = self.graph.create_node(
                name=f"call_{callee_name}",
                node_type="call",
                scope=self.current_scope
            )
            
            start_line, end_line = self._get_line_info(node)
            call_node.start_line = start_line
            call_node.end_line = end_line
            call_node.code_snippet = self._extract_snippet(node, 100)
            
            # Add CALLS edge
            self.graph.add_edge(
                call_node.id,
                target_id,
                EdgeType.CALLS,
                {"line": start_line}
            )
    
    def _process_variable(self, node):
        """Process variable declaration/assignment"""
        if not self.graph:
            return
            
        # Extract variable name(s)
        for child in node.children:
            if child.type in ['identifier', 'pattern']:
                var_name = self._extract_text(child).strip()
                
                if var_name and var_name not in self.variable_nodes:
                    # Create variable node
                    semantic_node = self.graph.create_node(
                        name=var_name,
                        node_type="variable",
                        scope=self.current_scope
                    )
                    
                    start_line, end_line = self._get_line_info(node)
                    semantic_node.start_line = start_line
                    semantic_node.end_line = end_line
                    semantic_node.code_snippet = self._extract_snippet(node, 100)
                    semantic_node.ast_node = node
                    
                    self.variable_nodes[var_name] = semantic_node.id
    
    def _process_decorator(self, node):
        """Process decorator"""
        if not self.graph:
            return
            
        decorator_name = self._extract_text(node).strip()
        
        semantic_node = self.graph.create_node(
            name=decorator_name,
            node_type="decorator",
            scope=self.current_scope
        )
        
        start_line, end_line = self._get_line_info(node)
        semantic_node.start_line = start_line
        semantic_node.end_line = end_line
        semantic_node.code_snippet = decorator_name
    
    def _extract_parameters(self, params_node) -> List[str]:
        """Extract parameter names from parameters node"""
        parameters = []
        
        def extract_param_name(node):
            if node.type in ['identifier', 'pattern']:
                return self._extract_text(node).strip()
            for child in node.children:
                result = extract_param_name(child)
                if result:
                    return result
            return None
        
        for child in params_node.children:
            if child.type not in ['(', ')', ',', 'comment']:
                param_name = extract_param_name(child)
                if param_name:
                    parameters.append(param_name)
        
        return parameters
    
    def _extract_inheritance(self, node, class_node_id: int):
        """Extract inheritance relationships"""
        if not self.graph:
            return
            
        for child in node.children:
            if child.type in ['identifier', 'type_identifier']:
                parent_name = self._extract_text(child).strip()
                
                # Check if parent class exists in graph
                if parent_name in self.class_nodes:
                    parent_id = self.class_nodes[parent_name]
                    self.graph.add_edge(
                        class_node_id,
                        parent_id,
                        EdgeType.INHERITS,
                        {"parent": parent_name}
                    )


def build_semantic_graph_from_ast(
    ast_root, 
    language: str = "python", 
    source_code: Optional[bytes] = None
) -> SemanticGraph:
    """
    Main entry point to build semantic graph from AST
    
    Args:
        ast_root: Root node of the tree-sitter AST
        language: Source language (python, javascript, typescript)
        source_code: Optional source code bytes
    
    Returns:
        SemanticGraph object
    """
    builder = SemanticGraphBuilder(language)
    return builder.build(ast_root, source_code)


def build_semantic_graph_from_all(
    ast_root,
    cfg,
    pdg,
    language: str = "python",
    source_code: Optional[bytes] = None
) -> SemanticGraph:
    """
    Build semantic graph enriched with CFG and PDG information
    
    Args:
        ast_root: AST root node
        cfg: Control Flow Graph
        pdg: Program Dependence Graph
        language: Source language
        source_code: Optional source code bytes
    
    Returns:
        Enriched SemanticGraph object
    """
    # Build base semantic graph from AST
    graph = build_semantic_graph_from_ast(ast_root, language, source_code)
    
    # TODO: Enrich with CFG information (control flow patterns)
    # TODO: Enrich with PDG information (data dependencies)
    
    return graph

