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
    start_line: Optional[int] = None  # Source line number where block starts
    end_line: Optional[int] = None    # Source line number where block ends
    code_snippet: str = ""            # Actual source code snippet (max 200 chars)
    
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
            "source_range": self.source_range,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "code_snippet": self.code_snippet
        }


class ControlFlowGraph:
    """Represents a Control Flow Graph"""
    
    def __init__(self, name: str = "main"):
        self.name = name
        self.blocks: Dict[int, BasicBlock] = {}
        self.entry_block_id: Optional[int] = None
        self.exit_block_id: Optional[int] = None
        self.next_block_id = 0
        self.post_dominators: Dict[int, Set[int]] = {}  # Post-dominance information
        
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
    
    def compute_post_dominators(self):
        """
        Compute post-dominance information.
        A node Y post-dominates X if all paths from X to EXIT go through Y.
        Uses reverse dataflow analysis from the exit node.
        """
        if self.exit_block_id is None:
            return
        
        # Initialize: exit post-dominates itself, all others post-dominate by all nodes
        all_blocks = set(self.blocks.keys())
        self.post_dominators = {}
        
        for block_id in all_blocks:
            if block_id == self.exit_block_id:
                self.post_dominators[block_id] = {block_id}
            else:
                self.post_dominators[block_id] = all_blocks.copy()
        
        # Iterate until fixpoint
        changed = True
        max_iterations = len(all_blocks) * 2
        iteration = 0
        
        while changed and iteration < max_iterations:
            changed = False
            iteration += 1
            
            for block_id in all_blocks:
                if block_id == self.exit_block_id:
                    continue
                
                # Post-dom(X) = {X} ∪ (∩ Post-dom(successor) for all successors)
                successors = self.blocks[block_id].successors
                
                if not successors:
                    # Dead end (no successors, not exit) - post-dominated by itself
                    new_post_dom = {block_id}
                else:
                    # Intersection of all successors' post-dominators
                    new_post_dom = all_blocks.copy()
                    for succ_id in successors:
                        if succ_id in self.post_dominators:
                            new_post_dom &= self.post_dominators[succ_id]
                    
                    # Add self
                    new_post_dom.add(block_id)
                
                if new_post_dom != self.post_dominators[block_id]:
                    self.post_dominators[block_id] = new_post_dom
                    changed = True
    
    def get_control_dependencies(self) -> Dict[int, List[int]]:
        """
        Compute control dependencies using post-dominance.
        
        A node Y is control-dependent on X if:
        1. There exists a path from X to Y
        2. Y post-dominates one (but not all) successors of X
        
        Returns:
            Dictionary mapping node_id -> list of nodes it is control-dependent on
        """
        if not self.post_dominators:
            self.compute_post_dominators()
        
        control_deps: Dict[int, List[int]] = {bid: [] for bid in self.blocks.keys()}
        
        # For each block X
        for x_id, x_block in self.blocks.items():
            successors = x_block.successors
            
            if len(successors) < 2:
                # No control dependency if only 0 or 1 successor
                continue
            
            # Check each successor
            for succ_id in successors:
                # Find blocks that are reachable from succ_id but not post-dominated by it
                reachable = self.get_reachable_blocks(succ_id)
                
                for y_id in reachable:
                    # Y is control-dependent on X if:
                    # - Y post-dominates succ_id
                    # - But Y does NOT post-dominate all successors of X
                    
                    if succ_id in self.post_dominators and y_id in self.post_dominators[succ_id]:
                        # Y post-dominates this successor
                        # Check if Y post-dominates ALL successors
                        post_dom_all = all(
                            s_id in self.post_dominators and y_id in self.post_dominators[s_id]
                            for s_id in successors
                        )
                        
                        if not post_dom_all and y_id != x_id:
                            # Y is control-dependent on X
                            if x_id not in control_deps[y_id]:
                                control_deps[y_id].append(x_id)
        
        return control_deps
    
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
        self.source_code: bytes = b""  # Store source code for extracting snippets
        
    def build(self, ast_root, source_code: Optional[bytes] = None) -> ControlFlowGraph:
        """Build CFG from AST root node"""
        if source_code:
            self.source_code = source_code
        elif hasattr(ast_root, 'text'):
            self.source_code = ast_root.text
        
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
        
        # Compute post-dominators for control dependency analysis
        cfg.compute_post_dominators()
        
        return cfg
    
    def _extract_code_snippet(self, node, max_length: int = 200) -> str:
        """Extract code snippet from AST node"""
        try:
            if hasattr(node, 'text'):
                text = node.text.decode('utf-8', errors='replace')
                # Clean up whitespace
                text = ' '.join(text.split())
                if len(text) > max_length:
                    return text[:max_length - 3] + "..."
                return text
        except Exception:
            pass
        return ""
    
    def _set_block_source_info(self, block: BasicBlock, node):
        """Set source line numbers and code snippet for a block"""
        if hasattr(node, 'start_point') and hasattr(node, 'end_point'):
            block.start_line = node.start_point[0] + 1  # Tree-sitter uses 0-indexed lines
            block.end_line = node.end_point[0] + 1
            block.source_range = (block.start_line, block.end_line)
        
        if not block.code_snippet:
            block.code_snippet = self._extract_code_snippet(node)
    
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
        
        elif node_type in ['while_statement', 'for_statement', 'for_in_statement']:
            return self._process_loop(node)
        
        elif node_type == 'return_statement':
            return self._process_return(node)
        
        elif node_type in ['function_definition', 'function_declaration', 'method_definition', 
                           'arrow_function', 'function', 'function_expression']:
            return self._process_function(node)
        
        elif node_type in ['try_statement', 'with_statement']:
            return self._process_exception_handling(node)
        
        elif node_type == 'break_statement':
            # Break statements need special handling in loop context
            if self.current_block is not None:
                self.current_block.ast_nodes.append(node)
                self._set_block_source_info(self.current_block, node)
            return []  # No continuation
        
        elif node_type == 'continue_statement':
            # Continue statements need special handling in loop context
            if self.current_block is not None:
                self.current_block.ast_nodes.append(node)
                self._set_block_source_info(self.current_block, node)
            return []  # No continuation
        
        # Statement-level nodes that should get their own blocks
        elif node_type in ['expression_statement', 'assignment', 'augmented_assignment',
                          'variable_declaration', 'lexical_declaration']:
            return self._process_statement(node)
        
        else:
            # Regular statement or container node
            if self.current_block is not None:
                self.current_block.ast_nodes.append(node)
                stmt_text = self._extract_code_snippet(node, 100)
                if stmt_text and stmt_text not in self.current_block.statements:
                    self.current_block.statements.append(stmt_text)
                self._set_block_source_info(self.current_block, node)
            
            # Process children for containers
            if node.child_count > 0:
                exit_blocks = parent_exit_blocks
                for child in node.children:
                    if child.type != 'comment':
                        child_exits = self._process_node(child, exit_blocks)
                        if child_exits:
                            exit_blocks = child_exits
                return exit_blocks
            
            return parent_exit_blocks
    
    def _process_statement(self, node) -> List[int]:
        """Process a single statement into its own block"""
        if self.current_cfg is None or self.current_block is None:
            raise RuntimeError("CFG or current block is None")
        
        # Create a new block for this statement
        stmt_block = self.current_cfg.create_block(BlockType.STATEMENT)
        self.current_cfg.add_edge(self.current_block.id, stmt_block.id)
        
        stmt_block.ast_nodes.append(node)
        stmt_block.statements.append(self._extract_code_snippet(node, 100))
        self._set_block_source_info(stmt_block, node)
        
        self.current_block = stmt_block
        return [stmt_block.id]
    
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
            elif child.type in ['block', 'body', 'suite', 'statement_block']:
                if consequence is None:
                    consequence = child
                else:
                    alternative = child
            elif child.type == 'else_clause':
                alternative = child
        
        if condition:
            condition_block.statements.append(self._extract_code_snippet(condition, 100))
            condition_block.ast_nodes.append(condition)
            self._set_block_source_info(condition_block, condition)
        else:
            self._set_block_source_info(condition_block, node)
        
        exit_blocks = []
        
        # Process consequence (then branch)
        if consequence:
            then_block = self.current_cfg.create_block(BlockType.STATEMENT)
            self.current_cfg.add_edge(condition_block.id, then_block.id)
            self.current_block = then_block
            self._set_block_source_info(then_block, consequence)
            
            # Process statements in the then branch
            then_exits = self._process_block_body(consequence)
            exit_blocks.extend(then_exits)
        
        # Process alternative (else branch)
        if alternative:
            else_block = self.current_cfg.create_block(BlockType.STATEMENT)
            self.current_cfg.add_edge(condition_block.id, else_block.id)
            self.current_block = else_block
            self._set_block_source_info(else_block, alternative)
            
            # Process statements in the else branch
            else_exits = self._process_block_body(alternative)
            exit_blocks.extend(else_exits)
        else:
            # No else branch, condition can fall through
            exit_blocks.append(condition_block.id)
        
        return exit_blocks
    
    def _process_block_body(self, node) -> List[int]:
        """Process a block body (suite, block, etc.) statement by statement"""
        if self.current_cfg is None or self.current_block is None:
            raise RuntimeError("CFG or current block is None")
        
        # Find all statement-level children
        statements = []
        for child in node.children:
            if child.type not in ['comment', '{', '}', ':', 'indent', 'dedent']:
                statements.append(child)
        
        if not statements:
            return [self.current_block.id]
        
        # Process each statement sequentially
        exit_blocks = [self.current_block.id]
        for stmt in statements:
            # Create new block for each statement
            stmt_exits = self._process_node(stmt, exit_blocks)
            if stmt_exits:
                exit_blocks = stmt_exits
            else:
                # Statement has no continuation (e.g., return, break)
                exit_blocks = []
                break
        
        return exit_blocks if exit_blocks else []
    
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
            if child.type in ['condition', 'parenthesized_expression', 'comparison_operator', 
                             'binary_operator', 'call_expression']:
                condition = child
            elif child.type in ['block', 'body', 'suite', 'statement_block']:
                body = child
        
        if condition:
            loop_header.statements.append(self._extract_code_snippet(condition, 100))
            loop_header.ast_nodes.append(condition)
            self._set_block_source_info(loop_header, condition)
        else:
            self._set_block_source_info(loop_header, node)
        
        # Process body
        if body:
            body_block = self.current_cfg.create_block(BlockType.LOOP_BODY)
            self.current_cfg.add_edge(loop_header.id, body_block.id)
            self.current_block = body_block
            self._set_block_source_info(body_block, body)
            
            # Process statements in loop body
            body_exits = self._process_block_body(body)
            
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
        return_block.statements.append(self._extract_code_snippet(node, 100))
        self._set_block_source_info(return_block, node)
        
        # Return statements go to exit
        self.current_cfg.add_edge(return_block.id, self.current_cfg.exit_block_id)
        return []  # No continuation after return
    
    def _process_function(self, node) -> List[int]:
        """
        Process function definitions - CRITICAL ENHANCEMENT
        Now decomposes function body into statement-level CFG blocks
        """
        if self.current_cfg is None or self.current_block is None:
            raise RuntimeError("CFG or current block is None")
            
        func_block = self.current_cfg.create_block(BlockType.FUNCTION)
        self.current_cfg.add_edge(self.current_block.id, func_block.id)
        
        # Extract function name
        func_name = "anonymous"
        for child in node.children:
            if child.type in ['identifier', 'property_identifier']:
                func_name = child.text.decode('utf-8', errors='replace')
                break
        
        func_block.statements.append(f"function {func_name}")
        func_block.ast_nodes.append(node)
        self._set_block_source_info(func_block, node)
        
        # Find and process function body
        body = None
        for child in node.children:
            if child.type in ['block', 'body', 'suite', 'statement_block']:
                body = child
                break
        
        if body:
            # Process function body statement by statement
            self.current_block = func_block
            body_exits = self._process_block_body(body)
            return body_exits
        
        return [func_block.id]
    
    def _process_exception_handling(self, node) -> List[int]:
        """Process try/except/finally blocks"""
        if self.current_cfg is None or self.current_block is None:
            raise RuntimeError("CFG or current block is None")
            
        try_block = self.current_cfg.create_block(BlockType.EXCEPTION)
        self.current_cfg.add_edge(self.current_block.id, try_block.id)
        self._set_block_source_info(try_block, node)
        
        exit_blocks = []
        
        for child in node.children:
            if child.type in ['block', 'body', 'suite', 'except_clause', 'finally_clause']:
                clause_block = self.current_cfg.create_block(BlockType.STATEMENT)
                self.current_cfg.add_edge(try_block.id, clause_block.id)
                self.current_block = clause_block
                self._set_block_source_info(clause_block, child)
                
                # Process statements in the clause
                clause_exits = self._process_block_body(child)
                exit_blocks.extend(clause_exits)
        
        return exit_blocks if exit_blocks else [try_block.id]


def build_cfg_from_ast(ast_root, language: str = "python", source_code: Optional[bytes] = None) -> ControlFlowGraph:
    """
    Main entry point to build CFG from AST
    
    Args:
        ast_root: Root node of the tree-sitter AST
        language: Source language (python, javascript, typescript)
        source_code: Optional source code bytes for extracting snippets
    
    Returns:
        ControlFlowGraph object
    """
    builder = CFGBuilder(language)
    return builder.build(ast_root, source_code)
