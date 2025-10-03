"""
Control Flow Graph (CFG) Builder
Builds a CFG from tree-sitter AST output
"""

from typing import Dict, List, Set, Optional, Any
from dataclasses import dataclass, field
from enum import Enum


class BlockType(Enum):
    """Types of basic blocks in the CFG"""
    ENTRY = "entry"
    EXIT = "exit"
    STATEMENT = "statement"
    CONDITION = "condition"
    LOOP_HEADER = "loop_header"
    LOOP_BODY = "loop_body"
    FUNCTION = "function"
    RETURN = "return"
    EXCEPTION = "exception"


@dataclass
class BasicBlock:
    """Represents a basic block in the CFG"""
    id: int
    type: BlockType
    statements: List[Any] = field(default_factory=list)
    successors: List[int] = field(default_factory=list)
    predecessors: List[int] = field(default_factory=list)
    ast_nodes: List[Any] = field(default_factory=list)
    source_range: Optional[tuple] = None  # (start_line, end_line)
    
    def add_successor(self, block_id: int):
        """Add a successor block"""
        if block_id not in self.successors:
            self.successors.append(block_id)
    
    def add_predecessor(self, block_id: int):
        """Add a predecessor block"""
        if block_id not in self.predecessors:
            self.predecessors.append(block_id)
    
    def to_dict(self) -> Dict:
        """Convert block to dictionary representation"""
        return {
            "id": self.id,
            "type": self.type.value,
            "statements": [str(stmt) for stmt in self.statements],
            "successors": self.successors,
            "predecessors": self.predecessors,
            "source_range": self.source_range
        }


class ControlFlowGraph:
    """Represents a Control Flow Graph"""
    
    def __init__(self, name: str = "main"):
        self.name = name
        self.blocks: Dict[int, BasicBlock] = {}
        self.entry_block_id: Optional[int] = None
        self.exit_block_id: Optional[int] = None
        self.next_block_id = 0
        
    def create_block(self, block_type: BlockType = BlockType.STATEMENT) -> BasicBlock:
        """Create a new basic block"""
        block = BasicBlock(id=self.next_block_id, type=block_type)
        self.blocks[self.next_block_id] = block
        self.next_block_id += 1
        return block
    
    def add_edge(self, from_block_id: int, to_block_id: int):
        """Add an edge between two blocks"""
        if from_block_id in self.blocks and to_block_id in self.blocks:
            self.blocks[from_block_id].add_successor(to_block_id)
            self.blocks[to_block_id].add_predecessor(from_block_id)
    
    def get_reachable_blocks(self, start_block_id: int) -> Set[int]:
        """Get all blocks reachable from the start block"""
        reachable = set()
        stack = [start_block_id]
        
        while stack:
            block_id = stack.pop()
            if block_id not in reachable and block_id in self.blocks:
                reachable.add(block_id)
                stack.extend(self.blocks[block_id].successors)
        
        return reachable
    
    def to_dict(self) -> Dict:
        """Convert CFG to dictionary representation"""
        return {
            "name": self.name,
            "entry_block": self.entry_block_id,
            "exit_block": self.exit_block_id,
            "blocks": {bid: block.to_dict() for bid, block in self.blocks.items()}
        }
    
    def to_dot(self) -> str:
        """Generate DOT format for visualization"""
        dot = [f'digraph "{self.name}" {{']
        dot.append('  rankdir=TB;')
        dot.append('  node [shape=box];')
        
        for block_id, block in self.blocks.items():
            label = f"{block.type.value}\\n{block_id}"
            if block.statements:
                stmt_preview = "\\n".join(str(s)[:30] for s in block.statements[:3])
                label += f"\\n{stmt_preview}"
            
            shape = "ellipse" if block.type in [BlockType.ENTRY, BlockType.EXIT] else "box"
            color = "green" if block.type == BlockType.ENTRY else "red" if block.type == BlockType.EXIT else "lightblue"
            
            dot.append(f'  {block_id} [label="{label}", shape={shape}, style=filled, fillcolor={color}];')
        
        for block_id, block in self.blocks.items():
            for succ_id in block.successors:
                dot.append(f'  {block_id} -> {succ_id};')
        
        dot.append('}')
        return '\n'.join(dot)


class CFGBuilder:
    """Builds CFG from tree-sitter AST"""
    
    def __init__(self, language: str = "python"):
        self.language = language
        self.current_cfg: Optional[ControlFlowGraph] = None
        self.current_block: Optional[BasicBlock] = None
        
    def build(self, ast_root) -> ControlFlowGraph:
        """Build CFG from AST root node"""
        cfg = ControlFlowGraph(name="main")
        self.current_cfg = cfg
        
        # Create entry and exit blocks
        entry = cfg.create_block(BlockType.ENTRY)
        exit_block = cfg.create_block(BlockType.EXIT)
        cfg.entry_block_id = entry.id
        cfg.exit_block_id = exit_block.id
        
        # Start building from entry
        self.current_block = cfg.create_block(BlockType.STATEMENT)
        cfg.add_edge(entry.id, self.current_block.id)
        
        # Process the AST
        exit_blocks = self._process_node(ast_root)
        
        # Connect all exit points to the exit block
        for exit_block_id in exit_blocks:
            cfg.add_edge(exit_block_id, cfg.exit_block_id)
        
        return cfg
    
    def _process_node(self, node, parent_exit_blocks: Optional[List[int]] = None) -> List[int]:
        """
        Process an AST node and return list of exit block IDs
        Returns blocks that should connect to the next statement
        """
        if parent_exit_blocks is None:
            if self.current_block is None:
                raise RuntimeError("Current block is None")
            parent_exit_blocks = [self.current_block.id]
        
        node_type = node.type
        
        # Control flow statements
        if node_type in ['if_statement', 'if_else_statement']:
            return self._process_if_statement(node)
        
        elif node_type in ['while_statement', 'for_statement']:
            return self._process_loop(node)
        
        elif node_type == 'return_statement':
            return self._process_return(node)
        
        elif node_type == 'function_definition':
            return self._process_function(node)
        
        elif node_type in ['try_statement', 'with_statement']:
            return self._process_exception_handling(node)
        
        elif node_type == 'break_statement':
            # Break statements need special handling in loop context
            if self.current_block is not None:
                self.current_block.ast_nodes.append(node)
            return []  # No continuation
        
        elif node_type == 'continue_statement':
            # Continue statements need special handling in loop context
            if self.current_block is not None:
                self.current_block.ast_nodes.append(node)
            return []  # No continuation
        
        else:
            # Regular statement
            if self.current_block is not None:
                self.current_block.ast_nodes.append(node)
                self.current_block.statements.append(node.text.decode('utf-8'))
            
            # Process children
            exit_blocks = [self.current_block.id] if self.current_block else []
            for child in node.children:
                if child.type != 'comment':
                    child_exits = self._process_node(child, exit_blocks)
                    if child_exits:
                        exit_blocks = child_exits
            
            return exit_blocks
    
    def _process_if_statement(self, node) -> List[int]:
        """Process if/else statements"""
        if self.current_cfg is None or self.current_block is None:
            raise RuntimeError("CFG or current block is None")
            
        condition_block = self.current_cfg.create_block(BlockType.CONDITION)
        self.current_cfg.add_edge(self.current_block.id, condition_block.id)
        
        # Find condition and bodies
        condition = None
        consequence = None
        alternative = None
        
        for child in node.children:
            if child.type in ['condition', 'parenthesized_expression']:
                condition = child
            elif child.type in ['block', 'body', 'suite']:
                if consequence is None:
                    consequence = child
                else:
                    alternative = child
            elif child.type == 'else_clause':
                alternative = child
        
        if condition:
            condition_block.statements.append(condition.text.decode('utf-8'))
            condition_block.ast_nodes.append(condition)
        
        exit_blocks = []
        
        # Process consequence (then branch)
        if consequence:
            then_block = self.current_cfg.create_block(BlockType.STATEMENT)
            self.current_cfg.add_edge(condition_block.id, then_block.id)
            self.current_block = then_block
            then_exits = self._process_node(consequence)
            exit_blocks.extend(then_exits)
        
        # Process alternative (else branch)
        if alternative:
            else_block = self.current_cfg.create_block(BlockType.STATEMENT)
            self.current_cfg.add_edge(condition_block.id, else_block.id)
            self.current_block = else_block
            else_exits = self._process_node(alternative)
            exit_blocks.extend(else_exits)
        else:
            # No else branch, condition can fall through
            exit_blocks.append(condition_block.id)
        
        return exit_blocks
    
    def _process_loop(self, node) -> List[int]:
        """Process loop statements"""
        if self.current_cfg is None or self.current_block is None:
            raise RuntimeError("CFG or current block is None")
            
        loop_header = self.current_cfg.create_block(BlockType.LOOP_HEADER)
        self.current_cfg.add_edge(self.current_block.id, loop_header.id)
        
        # Find condition and body
        condition = None
        body = None
        
        for child in node.children:
            if child.type in ['condition', 'parenthesized_expression', 'comparison_operator']:
                condition = child
            elif child.type in ['block', 'body', 'suite']:
                body = child
        
        if condition:
            loop_header.statements.append(condition.text.decode('utf-8'))
            loop_header.ast_nodes.append(condition)
        
        # Process body
        if body:
            body_block = self.current_cfg.create_block(BlockType.LOOP_BODY)
            self.current_cfg.add_edge(loop_header.id, body_block.id)
            self.current_block = body_block
            body_exits = self._process_node(body)
            
            # Loop back to header
            for exit_id in body_exits:
                self.current_cfg.add_edge(exit_id, loop_header.id)
        
        # Exit from loop (when condition is false)
        return [loop_header.id]
    
    def _process_return(self, node) -> List[int]:
        """Process return statements"""
        if self.current_cfg is None or self.current_block is None:
            raise RuntimeError("CFG or current block is None")
        if self.current_cfg.exit_block_id is None:
            raise RuntimeError("Exit block ID is None")
            
        return_block = self.current_cfg.create_block(BlockType.RETURN)
        self.current_cfg.add_edge(self.current_block.id, return_block.id)
        return_block.ast_nodes.append(node)
        return_block.statements.append(node.text.decode('utf-8'))
        
        # Return statements go to exit
        self.current_cfg.add_edge(return_block.id, self.current_cfg.exit_block_id)
        return []  # No continuation after return
    
    def _process_function(self, node) -> List[int]:
        """Process function definitions"""
        if self.current_cfg is None or self.current_block is None:
            raise RuntimeError("CFG or current block is None")
            
        func_block = self.current_cfg.create_block(BlockType.FUNCTION)
        self.current_cfg.add_edge(self.current_block.id, func_block.id)
        func_block.ast_nodes.append(node)
        
        # For now, treat function as a single block
        # In a more sophisticated implementation, we'd build a separate CFG for each function
        func_name = "unknown"
        for child in node.children:
            if child.type == 'identifier':
                func_name = child.text.decode('utf-8')
                break
        
        func_block.statements.append(f"function {func_name}")
        
        return [func_block.id]
    
    def _process_exception_handling(self, node) -> List[int]:
        """Process try/except/finally blocks"""
        if self.current_cfg is None or self.current_block is None:
            raise RuntimeError("CFG or current block is None")
            
        try_block = self.current_cfg.create_block(BlockType.EXCEPTION)
        self.current_cfg.add_edge(self.current_block.id, try_block.id)
        
        exit_blocks = []
        
        for child in node.children:
            if child.type in ['block', 'body', 'suite', 'except_clause', 'finally_clause']:
                clause_block = self.current_cfg.create_block(BlockType.STATEMENT)
                self.current_cfg.add_edge(try_block.id, clause_block.id)
                self.current_block = clause_block
                clause_exits = self._process_node(child)
                exit_blocks.extend(clause_exits)
        
        return exit_blocks if exit_blocks else [try_block.id]


def build_cfg_from_ast(ast_root, language: str = "python") -> ControlFlowGraph:
    """
    Main entry point to build CFG from AST
    
    Args:
        ast_root: Root node of the tree-sitter AST
        language: Source language (python, javascript, typescript)
    
    Returns:
        ControlFlowGraph object
    """
    builder = CFGBuilder(language)
    return builder.build(ast_root)
