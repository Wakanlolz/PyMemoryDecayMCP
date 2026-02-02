from mcp.server.fastmcp import FastMCP
import lancedb
import time
import json
import os
from datetime import datetime
import numpy as np
from sentence_transformers import SentenceTransformer

mcp = FastMCP("memory-decay")

# --- CONFIG ---
BASE_DATA_DIR = os.getenv("MEMORY_STORAGE_PATH", "./data")
DB_URI = os.path.join(BASE_DATA_DIR, "memory-lancedb")
JOURNAL_FILE = os.path.join(BASE_DATA_DIR, "permanent_journal.jsonl")  # The "Truth" file
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
DECAY_HALF_LIFE_HOURS = 24 * 7
MIN_STRENGTH_THRESHOLD = 0.2

# --- SETUP ---
if not os.path.exists(BASE_DATA_DIR):
    os.makedirs(BASE_DATA_DIR)

db = lancedb.connect(DB_URI)
model = SentenceTransformer(EMBEDDING_MODEL)

# Initialize LanceDB (The "Brain")
try:
    tbl = db.open_table("memories")
except:
    dummy_vec = model.encode("init").tolist()
    data = [
        {
            "vector": dummy_vec,
            "text": "init",
            "created_at": time.time(),
            "last_accessed": time.time(),
            "access_count": 1,
            "base_strength": 1.0,
        }
    ]
    tbl = db.create_table("memories", data=data, mode="overwrite")


# --- HELPER: The Decay Math ---
def calculate_strength(last_accessed, base_strength, access_count):
    elapsed_hours = (time.time() - last_accessed) / 3600
    decay = 2 ** (-elapsed_hours / DECAY_HALF_LIFE_HOURS)
    boost = np.log1p(access_count) * 0.1
    return min(base_strength * (decay + boost), 1.0)


# --- HELPER: The "Journal" Writer ---
def append_to_journal(content: str, metadata: dict):
    """Writes to the immutable ledger. This never deletes."""
    entry = {
        "timestamp": datetime.now().isoformat(),
        "content": content,
        "metadata": metadata,
    }
    with open(JOURNAL_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


# --- TOOLS ---


@mcp.tool()
def store_memory(content: str) -> str:
    """
    Stores a memory in BOTH the active brain (for thinking)
    and the permanent journal (for verification).
    """
    # 1. Write to Vector DB (The Brain)
    embedding = model.encode(content).tolist()
    tbl.add(
        [
            {
                "vector": embedding,
                "text": content,
                "created_at": time.time(),
                "last_accessed": time.time(),
                "access_count": 1,
                "base_strength": 1.0,
            }
        ]
    )

    # 2. Write to Flat File (The Journal)
    append_to_journal(content, {"type": "user_observation"})

    return "Memory stored in active recall and permanent ledger."


@mcp.tool()
def recall_memory(query: str) -> str:
    """
    Standard retrieval. Uses decay.
    WARNING: May yield incomplete info if memory is old.
    Use this for thinking/context.
    """
    embedding = model.encode(query).tolist()
    results = tbl.search(embedding).limit(10).to_pandas()

    if results.empty:
        return "No active memories found."

    valid = []
    for _, row in results.iterrows():
        strength = calculate_strength(
            row["last_accessed"], row["base_strength"], row["access_count"]
        )
        if strength >= MIN_STRENGTH_THRESHOLD:
            valid.append(f"[{strength:.2f}] {row['text']}")

    if not valid:
        return "Memories exist but have faded below threshold. Use verify_history for deep search."

    return "\n".join(valid)


@mcp.tool()
def verify_history(keyword: str, date_filter: str = None) -> str:
    """
    AUDIT TOOL. Bypasses all decay logic.
    Reads the raw permanent_journal.jsonl file.
    Use this when the user challenges your memory or asks 'Did I say that?'.
    SLOW operation.
    """
    matches = []
    try:
        with open(JOURNAL_FILE, "r", encoding="utf-8") as f:
            for line in f:
                entry = json.loads(line)
                # Simple string matching (or add regex logic here)
                if keyword.lower() in entry["content"].lower():
                    matches.append(f"[{entry['timestamp']}] {entry['content']}")
    except FileNotFoundError:
        return "No journal found."

    if not matches:
        return "No record found in permanent journal."

    return "VERIFICATION RECORD:\n" + "\n".join(matches[-10:])  # Return last 10 matches


if __name__ == "__main__":
    mcp.run()
