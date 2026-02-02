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
JOURNAL_FILE = os.path.join(BASE_DATA_DIR, "permanent_journal.jsonl")
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
MIN_STRENGTH_THRESHOLD = 0.15

# Domain-Specific Half-Lives (in hours)
DECAY_CONFIG = {
    "episodic": 24 * 7,      # 1 week: Events, logs, temporary context
    "semantic": 24 * 30,     # 1 month: General facts, user preferences
    "procedural": 24 * 365,  # 1 year: Skills, workflows, code patterns
}

# --- SETUP ---
if not os.path.exists(BASE_DATA_DIR):
    os.makedirs(BASE_DATA_DIR)

db = lancedb.connect(DB_URI)
model = SentenceTransformer(EMBEDDING_MODEL)

# Initialize LanceDB
try:
    tbl = db.open_table("memories")
    # Ensure category field exists (migration for older versions)
    if "category" not in tbl.schema.names:
        df = tbl.to_pandas()
        df["category"] = "semantic"
        tbl = db.create_table("memories", data=df, mode="overwrite")
except:
    dummy_vec = model.encode("init").tolist()
    data = [
        {
            "vector": dummy_vec,
            "text": "init",
            "category": "semantic",
            "created_at": time.time(),
            "last_accessed": time.time(),
            "access_count": 1,
            "base_strength": 1.0,
        }
    ]
    tbl = db.create_table("memories", data=data, mode="overwrite")


# --- HELPER: The Decay & Reinforcement Math ---
def calculate_strength(last_accessed, base_strength, access_count, category):
    half_life = DECAY_CONFIG.get(category, DECAY_CONFIG["episodic"])
    elapsed_hours = (time.time() - last_accessed) / 3600
    
    # Retrieval Strength (Decays)
    decay = 2 ** (-elapsed_hours / half_life)
    
    # Hebbian Boost (Learning through retrieval)
    boost = np.log1p(access_count) * 0.15
    
    return min(base_strength * (decay + boost), 1.0)


def append_to_journal(content: str, metadata: dict):
    entry = {
        "timestamp": datetime.now().isoformat(),
        "content": content,
        "metadata": metadata,
    }
    with open(JOURNAL_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


# --- TOOLS ---

@mcp.tool()
def store_memory(content: str, category: str = "episodic") -> str:
    """
    Stores a memory with a specific category (episodic, semantic, procedural).
    - episodic: Short-term context (logs, current tasks).
    - semantic: Facts, preferences, user identity.
    - procedural: Code patterns, logic, workflows.
    """
    category = category.lower() if category.lower() in DECAY_CONFIG else "episodic"
    embedding = model.encode(content).tolist()
    
    tbl.add(
        [
            {
                "vector": embedding,
                "text": content,
                "category": category,
                "created_at": time.time(),
                "last_accessed": time.time(),
                "access_count": 1,
                "base_strength": 1.0,
            }
        ]
    )

    append_to_journal(content, {"type": "user_observation", "category": category})
    return f"Stored as {category} memory."


@mcp.tool()
def recall_memory(query: str) -> str:
    """
    Retrieves memories based on semantic relevance and decay.
    Successfully recalled memories receive a 'Hebbian boost', refreshing their strength.
    """
    embedding = model.encode(query).tolist()
    results = tbl.search(embedding).limit(5).to_pandas()

    if results.empty:
        return "No active memories found."

    valid_responses = []
    to_boost = [] # List of (text, current_access_count)

    for _, row in results.iterrows():
        strength = calculate_strength(
            row["last_accessed"], row["base_strength"], row["access_count"], row["category"]
        )
        
        if strength >= MIN_STRENGTH_THRESHOLD:
            valid_responses.append(f"[{row['category'].upper()} | Strength: {strength:.2f}] {row['text']}")
            to_boost.append((row["text"], row["access_count"])) 

    # Reinforcement Learning: Update accessed memories
    if to_boost:
        now = time.time()
        for text, current_count in to_boost:
            # In a real app, we'd use a unique ID. Here we filter by text for simplicity.
            tbl.update(where=f'text = "{text}"', values={"last_accessed": now, "access_count": current_count + 1})

    if not valid_responses:
        return "Relevant memories have faded. Try 'verify_history' for archival search."

    return "\n".join(valid_responses)


@mcp.tool()
def verify_history(keyword: str) -> str:
    """
    Bypasses decay to search the immutable Archive. Use for audit or when recall fails.
    """
    matches = []
    try:
        with open(JOURNAL_FILE, "r", encoding="utf-8") as f:
            for line in f:
                entry = json.loads(line)
                if keyword.lower() in entry["content"].lower():
                    matches.append(f"[{entry['timestamp']}] {entry['content']}")
    except FileNotFoundError:
        return "Archive is empty."

    return "ARCHIVE RECORD:\n" + "\n".join(matches[-10:]) if matches else "No matching record."

if __name__ == "__main__":
    mcp.run()