"""
Program Dependence Graph (PDG) Builder
Builds a PDG from CFG and AST, tracking data and control dependencies
"""

from typing import Dict, List, Set, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from cfg.cfg_builder import ControlFlowGraph, BasicBlock, BlockType

class DependenceType(Enum):
    """Types of dependencies in the PDG"""
    DATA = "data"              # Data dependency (def-use)
    CONTROL = "control"        # Control dependency
    CALL = "call"              # Function call dependency
    PARAMETER = "parameter"    # Parameter passing


@dataclass
class Variable:
    """Represents a variable in the program"""
    name: str
    scope: str = "global"
    type_hint: Optional[str] = None
    definition_nodes: List[int] = field(default_factory=list)
    use_nodes: List[int] = field(default_factory=list)


@dataclass
class PDGNode:
    """Node in the Program Dependence Graph"""
    id: int
    block_id: Optional[int] = None  # Reference to CFG block
    statement: str = ""
    ast_node: Any = None
    node_type: str = "statement"
    start_line: Optional[int] = None  # Source line number
    end_line: Optional[int] = None
    code_snippet: str = ""  # Source code snippet
    
    # Dependencies
    data_dependencies: List[int] = field(default_factory=list)  # Nodes this depends on (data)
    control_dependencies: List[int] = field(default_factory=list)  # Nodes this depends on (control)
    
    # Variables
    defines: Set[str] = field(default_factory=set)  # Variables defined
    uses: Set[str] = field(default_factory=set)     # Variables used
    
    def add_data_dependency(self, node_id: int):
        """Add a data dependency"""
        if node_id not in self.data_dependencies:
            self.data_dependencies.append(node_id)
    
    def add_control_dependency(self, node_id: int):
        """Add a control dependency"""
        if node_id not in self.control_dependencies:
            self.control_dependencies.append(node_id)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "block_id": self.block_id,
            "statement": self.statement[:100],  # Truncate long statements
            "node_type": self.node_type,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "code_snippet": self.code_snippet[:200],  # Max 200 chars for AI readability
            "defines": list(self.defines),
            "uses": list(self.uses),
            "data_dependencies": self.data_dependencies,
            "control_dependencies": self.control_dependencies
        }


class ProgramDependenceGraph:
    """Program Dependence Graph"""
    
    def __init__(self, name: str = "main"):
        self.name = name
        self.nodes: Dict[int, PDGNode] = {}
        self.variables: Dict[str, Variable] = {}
        self.entry_node_id: Optional[int] = None
        self.next_node_id = 0
        self.reaching_defs: Dict[int, Dict[str, Set[int]]] = {}  # node_id -> {var -> set of def nodes}
        
    def create_node(self, statement: str = "", node_type: str = "statement") -> PDGNode:
        """Create a new PDG node"""
        node = PDGNode(id=self.next_node_id, statement=statement, node_type=node_type)
        self.nodes[self.next_node_id] = node
        self.next_node_id += 1
        return node
    
    def add_variable(self, name: str, scope: str = "global") -> Variable:
        """Add or get a variable"""
        key = f"{scope}:{name}"
        if key not in self.variables:
            self.variables[key] = Variable(name=name, scope=scope)
        return self.variables[key]
    
    def compute_reaching_definitions(self, cfg: 'ControlFlowGraph'):
        """
        Compute reaching definitions using iterative dataflow analysis.
        
        For each program point, determine which definitions of each variable
        can reach that point along some path.
        
        Uses standard forward dataflow algorithm:
        - gen[B] = variables defined in block B
        - kill[B] = definitions of same variables killed by B
        - in[B] = union of out[P] for all predecessors P
        - out[B] = gen[B] ∪ (in[B] - kill[B])
        """
        from cfg.cfg_builder import ControlFlowGraph, BasicBlock
        
        # Initialize reaching definitions for each block
        reaching_in: Dict[int, Dict[str, Set[int]]] = {}
        reaching_out: Dict[int, Dict[str, Set[int]]] = {}
        
        # Get all blocks and initialize
        for block_id in cfg.blocks.keys():
            reaching_in[block_id] = {}
            reaching_out[block_id] = {}
        
        # Compute gen and kill sets for each block
        gen: Dict[int, Dict[str, int]] = {}  # block -> {var -> def_node}
        
        for block_id, pdg_node in self.nodes.items():
            if pdg_node.block_id is not None:
                gen[pdg_node.block_id] = {}
                for var in pdg_node.defines:
                    gen[pdg_node.block_id][var] = pdg_node.id
        
        # Iterative dataflow analysis
        changed = True
        max_iterations = len(cfg.blocks) * 3
        iteration = 0
        
        while changed and iteration < max_iterations:
            changed = False
            iteration += 1
            
            for block_id, block in cfg.blocks.items():
                # in[B] = union of out[P] for all predecessors
                new_in: Dict[str, Set[int]] = {}
                
                for pred_id in block.predecessors:
                    if pred_id in reaching_out:
                        for var, defs in reaching_out[pred_id].items():
                            if var not in new_in:
                                new_in[var] = set()
                            new_in[var].update(defs)
                
                if new_in != reaching_in[block_id]:
                    reaching_in[block_id] = new_in
                    changed = True
                
                # out[B] = gen[B] ∪ (in[B] - kill[B])
                new_out = {var: defs.copy() for var, defs in new_in.items()}
                
                # Apply gen (overwrite with new definitions)
                if block_id in gen:
                    for var, def_node in gen[block_id].items():
                        new_out[var] = {def_node}
                
                if new_out != reaching_out[block_id]:
                    reaching_out[block_id] = new_out
                    changed = True
        
        # Store reaching definitions for PDG nodes
        for node_id, pdg_node in self.nodes.items():
            if pdg_node.block_id is not None and pdg_node.block_id in reaching_in:
                self.reaching_defs[node_id] = reaching_in[pdg_node.block_id].copy()
    
    def get_reaching_definitions(self, variable: str, at_node: int) -> List[int]:
        """Get all definitions of a variable that reach a given node"""
        if at_node in self.reaching_defs:
            var_key_global = f"global:{variable}"
            
            # Check reaching defs computed by dataflow
            if variable in self.reaching_defs[at_node]:
                return list(self.reaching_defs[at_node][variable])
            
            # Fallback: check variable's definition list
            if var_key_global in self.variables:
                return self.variables[var_key_global].definition_nodes
        
        # Fallback to global definitions
        var_key = f"global:{variable}"
        if var_key in self.variables:
            return self.variables[var_key].definition_nodes
        
        return []
    
    def to_dict(self) -> Dict:
        """Convert PDG to dictionary"""
        return {
            "name": self.name,
            "entry_node": self.entry_node_id,
            "nodes": {nid: node.to_dict() for nid, node in self.nodes.items()},
            "variables": {
                name: {
                    "name": var.name,
                    "scope": var.scope,
                    "definitions": var.definition_nodes,
                    "uses": var.use_nodes
                }
                for name, var in self.variables.items()
            }
        }
    
    def to_dot(self) -> str:
        """Generate DOT format for visualization"""
        dot = [f'digraph "{self.name}_PDG" {{']
        dot.append('  rankdir=TB;')
        dot.append('  node [shape=box];')
        
        # Nodes
        for node_id, node in self.nodes.items():
            label = f"{node.node_type}\\n{node_id}"
            if node.statement:
                stmt_preview = node.statement[:40].replace('"', '\\"')
                label += f"\\n{stmt_preview}"
            if node.defines:
                label += f"\\nDEF: {', '.join(list(node.defines)[:3])}"
            if node.uses:
                label += f"\\nUSE: {', '.join(list(node.uses)[:3])}"
            
            color = "lightgreen" if node.node_type == "entry" else "lightblue"
            dot.append(f'  {node_id} [label="{label}", style=filled, fillcolor={color}];')
        
        # Edges
        for node_id, node in self.nodes.items():
            # Data dependencies (solid blue)
            for dep_id in node.data_dependencies:
                dot.append(f'  {dep_id} -> {node_id} [color=blue, label="data"];')
            
            # Control dependencies (dashed red)
            for dep_id in node.control_dependencies:
                dot.append(f'  {dep_id} -> {node_id} [color=red, style=dashed, label="ctrl"];')
        
        dot.append('}')
        return '\n'.join(dot)


class PDGBuilder:
    """Builds PDG from CFG and AST"""
    
    def __init__(self, cfg: ControlFlowGraph, language: str = "python"):
        self.cfg = cfg
        self.language = language
        self.pdg: Optional[ProgramDependenceGraph] = None
        self.block_to_node: Dict[int, int] = {}  # Map CFG blocks to PDG nodes
    
    def _require_pdg(self) -> ProgramDependenceGraph:
        """Ensure that a PDG instance is available"""
        if self.pdg is None:
            raise RuntimeError("PDG has not been initialized; call build() before using PDGBuilder helpers.")
        return self.pdg
        
    def build(self) -> ProgramDependenceGraph:
        """Build PDG from CFG with enhanced control and data dependency analysis"""
        pdg = ProgramDependenceGraph(name=self.cfg.name)
        self.pdg = pdg
        
        # Create entry node
        entry = pdg.create_node(statement="ENTRY", node_type="entry")
        pdg.entry_node_id = entry.id
        
        # Create PDG nodes from CFG blocks
        for block_id, block in self.cfg.blocks.items():
            pdg_node = self._create_pdg_node_from_block(block)
            self.block_to_node[block_id] = pdg_node.id
        
        # Compute reaching definitions using dataflow analysis
        pdg.compute_reaching_definitions(self.cfg)
        
        # Compute control dependencies using post-dominance
        self._compute_control_dependencies()
        
        # Compute data dependencies using reaching definitions
        self._compute_data_dependencies()
        
        return pdg
    
    def _create_pdg_node_from_block(self, block: BasicBlock) -> PDGNode:
        """Create PDG node from CFG block with line numbers and code snippets"""
        statement = " ".join(block.statements) if block.statements else f"Block {block.id}"
        pdg = self._require_pdg()
        node = pdg.create_node(statement=statement, node_type=block.type.value)
        node.block_id = block.id
        
        # Copy line numbers and code snippet from CFG block
        node.start_line = block.start_line
        node.end_line = block.end_line
        node.code_snippet = block.code_snippet
        
        # Extract variables defined and used
        for ast_node in block.ast_nodes:
            self._extract_variables(ast_node, node)
        
        return node
    def _extract_variables(self, ast_node, pdg_node: PDGNode, visited: Optional[Set[int]] = None):
        """Extract variables defined and used in an AST node"""
        if not ast_node:
            return
        
        # Initialize visited set on first call to prevent duplicate tracking
        if visited is None:
            visited = set()
        
        # Skip if we've already processed this node
        node_id = id(ast_node)
        if node_id in visited:
            return
        visited.add(node_id)
        
        pdg = self._require_pdg()
        node_type = ast_node.type
        
        # Assignments (definitions)
        if node_type in ['assignment', 'augmented_assignment', 'assignment_expression']:
            # Left side is defined
            for child in ast_node.children:
                if child.type in ['identifier', 'pattern']:
                    var_name = child.text.decode('utf-8')
                    pdg_node.defines.add(var_name)
                    var = pdg.add_variable(var_name)
                    if pdg_node.id not in var.definition_nodes:
                        var.definition_nodes.append(pdg_node.id)
                    break
            
            # Right side is used
            for child in ast_node.children:
                if child.type == 'expression' or child.type == 'identifier':
                    self._extract_uses(child, pdg_node, visited)
        
        # Function parameters (definitions)
        elif node_type in ['parameters', 'parameter']:
            for child in ast_node.children:
                if child.type == 'identifier':
                    var_name = child.text.decode('utf-8')
                    pdg_node.defines.add(var_name)
                    var = pdg.add_variable(var_name)
                    if pdg_node.id not in var.definition_nodes:
                        var.definition_nodes.append(pdg_node.id)
        
        # Regular uses
        elif node_type == 'identifier':
            var_name = ast_node.text.decode('utf-8')
            # Check if it's not a function name or keyword
            if var_name not in ['def', 'class', 'if', 'for', 'while', 'return']:
                pdg_node.uses.add(var_name)
                var = pdg.add_variable(var_name)
                if pdg_node.id not in var.use_nodes:
                    var.use_nodes.append(pdg_node.id)
        
        # Recurse on children
        for child in ast_node.children:
            self._extract_variables(child, pdg_node, visited)
    def _extract_uses(self, ast_node, pdg_node: PDGNode, visited: Optional[Set[int]] = None):
        """Extract variable uses from an expression"""
        if not ast_node:
            return
        
        # Initialize visited set on first call
        if visited is None:
            visited = set()
        
        # Skip if already processed
        node_id = id(ast_node)
        if node_id in visited:
            return
        visited.add(node_id)
        
        pdg = self._require_pdg()
        if ast_node.type == 'identifier':
            var_name = ast_node.text.decode('utf-8')
            pdg_node.uses.add(var_name)
            var = pdg.add_variable(var_name)
            if pdg_node.id not in var.use_nodes:
                var.use_nodes.append(pdg_node.id)
        
        for child in ast_node.children:
            self._extract_uses(child, pdg_node, visited)
    def _compute_control_dependencies(self):
        """
        Compute control dependencies using post-dominance from CFG.
        
        A node Y is control-dependent on X if:
        1. There exists a path from X to Y
        2. Y post-dominates one (but not all) successors of X
        
        Uses the CFG's post-dominance analysis.
        """
        pdg = self._require_pdg()
        
        # Get control dependencies from CFG
        control_deps = self.cfg.get_control_dependencies()
        
        # Map control dependencies from CFG blocks to PDG nodes
        for y_block_id, x_block_ids in control_deps.items():
            if y_block_id in self.block_to_node:
                y_node_id = self.block_to_node[y_block_id]
                y_node = pdg.nodes.get(y_node_id)
                
                if y_node is not None:
                    for x_block_id in x_block_ids:
                        if x_block_id in self.block_to_node:
                            x_node_id = self.block_to_node[x_block_id]
                            y_node.add_control_dependency(x_node_id)
    
    def _compute_data_dependencies(self):
        """
        Compute data dependencies using reaching definitions.
        
        For each variable USE, find the reaching DEF using dataflow analysis.
        Creates def-use chains with statement-level granularity.
        """
        pdg = self._require_pdg()
        
        # For each node that uses a variable
        for node_id, node in pdg.nodes.items():
            for var_used in node.uses:
                # Find all definitions that reach this use
                reaching_defs = pdg.get_reaching_definitions(var_used, node_id)
                
                # Add data dependencies
                for def_node_id in reaching_defs:
                    if def_node_id != node_id:  # Don't depend on self
                        node.add_data_dependency(def_node_id)


def build_pdg_from_cfg(cfg: ControlFlowGraph, language: str = "python") -> ProgramDependenceGraph:
    """
    Main entry point to build PDG from CFG
    
    Args:
        cfg: Control Flow Graph
        language: Source language (python, javascript, typescript)
    
    Returns:
        ProgramDependenceGraph object
    """
    builder = PDGBuilder(cfg, language)
    return builder.build()


def build_pdg_from_ast(ast_root, language: str = "python") -> Tuple[ControlFlowGraph, ProgramDependenceGraph]:
    """
    Build both CFG and PDG from AST
    
    Args:
        ast_root: Root node of the tree-sitter AST
        language: Source language (python, javascript, typescript)
    
    Returns:
        Tuple of (ControlFlowGraph, ProgramDependenceGraph)
    """
    from cfg.cfg_builder import build_cfg_from_ast
    
    cfg = build_cfg_from_ast(ast_root, language)
    pdg = build_pdg_from_cfg(cfg, language)
    
    return cfg, pdg
