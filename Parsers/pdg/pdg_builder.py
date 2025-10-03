"""
Program Dependence Graph (PDG) Builder
Builds a PDG from CFG and AST, tracking data and control dependencies
"""

from typing import Dict, List, Set, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from cfg.cfg_builder import ControlFlowGraph, BasicBlock

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
    
    def get_reaching_definitions(self, variable: str, at_node: int) -> List[int]:
        """Get all definitions of a variable that reach a given node"""
        var_key = f"global:{variable}"  # Simplified: assume global scope
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
        """Build PDG from CFG"""
        pdg = ProgramDependenceGraph(name=self.cfg.name)
        self.pdg = pdg
        
        # Create entry node
        entry = pdg.create_node(statement="ENTRY", node_type="entry")
        pdg.entry_node_id = entry.id
        
        # Create PDG nodes from CFG blocks
        for block_id, block in self.cfg.blocks.items():
            pdg_node = self._create_pdg_node_from_block(block)
            self.block_to_node[block_id] = pdg_node.id
        
        # Compute control dependencies
        self._compute_control_dependencies()
        
        return pdg
    
    def _create_pdg_node_from_block(self, block: BasicBlock) -> PDGNode:
        """Create PDG node from CFG block"""
        statement = " ".join(block.statements) if block.statements else f"Block {block.id}"
        pdg = self._require_pdg()
        node = pdg.create_node(statement=statement, node_type=block.type.value)
        node.block_id = block.id
        
        # Extract variables defined and used
        for ast_node in block.ast_nodes:
            self._extract_variables(ast_node, node)
        
        return node
    def _extract_variables(self, ast_node, pdg_node: PDGNode):
        """Extract variables defined and used in an AST node"""
        if not ast_node:
            return
        
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
                    var.definition_nodes.append(pdg_node.id)
                    break
            
            # Right side is used
            for child in ast_node.children:
                if child.type == 'expression' or child.type == 'identifier':
                    self._extract_uses(child, pdg_node)
        
        # Function parameters (definitions)
        elif node_type in ['parameters', 'parameter']:
            for child in ast_node.children:
                if child.type == 'identifier':
                    var_name = child.text.decode('utf-8')
                    pdg_node.defines.add(var_name)
                    var = pdg.add_variable(var_name)
                    var.definition_nodes.append(pdg_node.id)
        
        # Regular uses
        elif node_type == 'identifier':
            var_name = ast_node.text.decode('utf-8')
            # Check if it's not a function name or keyword
            if var_name not in ['def', 'class', 'if', 'for', 'while', 'return']:
                pdg_node.uses.add(var_name)
                var = pdg.add_variable(var_name)
                var.use_nodes.append(pdg_node.id)
        
        # Recurse on children
        for child in ast_node.children:
            self._extract_variables(child, pdg_node)
    def _extract_uses(self, ast_node, pdg_node: PDGNode):
        """Extract variable uses from an expression"""
        if not ast_node:
            return
        
        pdg = self._require_pdg()
        if ast_node.type == 'identifier':
            var_name = ast_node.text.decode('utf-8')
            pdg_node.uses.add(var_name)
            var = pdg.add_variable(var_name)
            var.use_nodes.append(pdg_node.id)
        
        for child in ast_node.children:
            self._extract_uses(child, pdg_node)
    def _compute_control_dependencies(self):
        """Compute control dependencies using post-dominance"""
        # Simplified control dependency computation
        # A node Y is control dependent on X if:
        # 1. There exists a path from X to Y
        # 2. Y post-dominates all successors of X except for one
        
        # For simplicity, we use a heuristic:
        # If a block is in a conditional branch, it depends on the condition
        
        pdg = self._require_pdg()
        for block_id, block in self.cfg.blocks.items():
            if block_id not in self.block_to_node:
                continue
            
            pdg_node_id = self.block_to_node[block_id]
            pdg_node = pdg.nodes[pdg_node_id]
        # For simplicity, we use a heuristic:
        # If a block is in a conditional branch, it depends on the condition
        
        for block_id, block in self.cfg.blocks.items():
            if block_id not in self.block_to_node:
                continue

            pdg_node_id = self.block_to_node[block_id]
            pdg_node = pdg.nodes.get(pdg_node_id)
            if pdg_node is None:
                continue
            
    def _compute_data_dependencies(self):
        """Compute data dependencies using reaching definitions"""
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
