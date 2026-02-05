# PyMemoryDecay MCP

A Model Context Protocol (MCP) server that implements memory with decay mechanics. Memories fade over time unless accessed, mimicking human memory retention. It also includes a permanent "journal" for verification.

## Why This?
Inspired by https://www.moltbook.com/post/783de11a-2937-4ab2-a23e-4227360b126f
## Prerequisites

- [uv](https://github.com/astral-sh/uv) (Fast Python package installer and resolver)
- Python 3.12+

## Setup

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd PyMemoryDecayMCP
   ```

2. **Install dependencies:**
   Initialize the project and install dependencies using `uv`:
   ```bash
   uv sync
   ```

## Running Locally

To run the MCP server from source:

```bash
uv run main.py
```

## Building the Executable

To compile the project into a single standalone executable (`.exe`):

1. **Add development dependencies (if not already added):**
   ```bash
   uv add --dev pyinstaller
   ```

2. **Build:**
   ```bash
   uv run pyinstaller --onefile main.py --name memory-decay-mcp --clean
   ```

3. **Locate the executable:**
   The compiled `.exe` will be found in the `dist/` directory:
   `dist/memory-decay-mcp.exe`

## VS Code Configuration

To use this with the VS Code MCP extension, add the following to your `mcp.json` config file (typically found in `%APPDATA%\Code\User\globalStorage\mcp-server\mcp.json` or configured via the extension settings).

### Using Source (Recommended for Dev)
```json
{
  "mcpServers": {
    "memory-decay": {
      "command": "uv",
      "args": [
        "run",
        "C:\\path\\to\\PyMemoryDecayMCP\\main.py"
      ],
      "env": {
        "MEMORY_STORAGE_PATH": "C:\\path\\to\\custom\\data\\folder"
      }
    }
  }
}
```

### Using Built Executable
```json
{
  "mcpServers": {
    "memory-decay": {
      "command": "C:\\path\\to\\PyMemoryDecayMCP\\dist\\memory-decay-mcp.exe",
      "args": [],
      "env": {
        "MEMORY_STORAGE_PATH": "C:\\path\\to\\custom\\data\\folder"
      }
    }
  }
}
```

## Configuration

- **MEMORY_STORAGE_PATH**: (Optional) Environment variable to set the directory where the vector database and journal file are stored. Defaults to `./data` relative to the working directory.

## Features

- **Store Memory**: Embeds text and stores it in LanceDB.
- **Recall Memory**:Retrieves relevant memories based on semantic search, filtered by memory "strength" (decay function).
- **Verify History**: An immutable audit log (flat file) to verify facts regardless of memory decay.
