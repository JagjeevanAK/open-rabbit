FROM e2bdev/code-interpreter:latest

WORKDIR /home/user

# Install tree-sitter for code parsing inside sandbox
# This enables AST parsing without needing to transfer files back to the backend
RUN pip install --no-cache-dir \
    tree-sitter>=0.25.2 \
    tree-sitter-python>=0.23.0 \
    tree-sitter-javascript>=0.23.0 \
    tree-sitter-typescript>=0.23.0

# Create repos directory for cloned repositories
RUN mkdir -p /home/user/repos

# Set default working directory for cloned repos
WORKDIR /home/user/repos