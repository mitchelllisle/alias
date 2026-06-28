"""priveil MCP server — optional extra.

Install with::

    pip install "priveil[mcp]"
"""

# isort: skip_file
# server must be imported first — it owns the ImportError guard for the mcp extra.
from priveil.mcp.server import main, mcp  # noqa: F401
import priveil.mcp.tools as _tools  # noqa: F401 — triggers @mcp.tool() registration

__all__ = ["mcp", "main"]
