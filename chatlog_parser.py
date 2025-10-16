#!/opt/homebrew/bin/python3.11
import sys
import json
import asyncio
from pathlib import Path
from dotenv import load_dotenv
from transformers import pipeline

# -----------------------------
# Load environment configuration
# -----------------------------
load_dotenv()

# Load Phi-3 Mini (4k context) locally
llm = pipeline(
    "text-generation",
    model="microsoft/phi-3-mini-4k-instruct",
    device_map="auto",
    torch_dtype="auto",
)

SYSTEM_PROMPT = "Extract all user/assistant messages and metadata as JSON."

# -----------------------------
# Helpers
# -----------------------------
def load_chat_text(export_path: str) -> str:
    """Load chat export JSON and flatten into text."""
    path = Path(export_path)
    if not path.exists():
        raise FileNotFoundError(f"Chat export file not found: {export_path}")

    data = json.load(path.open())
    messages = []

    for convo in data:
        mapping = convo.get("mapping", {})
        for node in mapping.values():
            msg = node.get("message")
            if msg and "content" in msg:
                parts = msg["content"].get("parts", [])
                if parts:
                    clean_parts = []
                    for p in parts:
                        if isinstance(p, str):
                            clean_parts.append(p)
                        elif isinstance(p, dict):
                            clean_parts.append(json.dumps(p))
                    messages.append("\n".join(clean_parts))

    return "\n".join(messages)

def chunk_text(text: str, max_chars: int = 8000) -> list[str]:
    """Chunk text into safe model-length pieces."""
    return [text[i:i + max_chars] for i in range(0, len(text), max_chars)]

# -----------------------------
# Async LLM Analysis
# -----------------------------
async def analyze_chunk(chunk: str, idx: int):
    """Send one chunk to local Phi-3 for analysis."""
    try:
        prompt = f"{SYSTEM_PROMPT}\n\nUser Data:\n{chunk}"
        result = await asyncio.to_thread(
            llm,
            prompt,
            max_new_tokens=512,
            do_sample=False,
        )
        result = result[0]["generated_text"]
        print(f"[DEBUG] Processed chunk {idx} → {len(result)} chars extracted")
        return {"chunk": idx, "result": result}
    except Exception as e:
        print(f"[ERROR] Chunk {idx} failed: {e}")
        return {"chunk": idx, "error": str(e)}

async def process_all_chunks(chunks: list[str], concurrency: int = 1, checkpoint_every: int = 50):
    """Process all chunks sequentially with checkpointing."""
    results = []
    for i, ch in enumerate(chunks):
        res = await analyze_chunk(ch, i)
        results.append(res)

        # Save checkpoint every N chunks
        if (i + 1) % checkpoint_every == 0:
            cp_path = Path(f"analysis_results_checkpoint_{i+1}.json")
            with cp_path.open("w") as f:
                json.dump(results, f, indent=2)
            print(f"[CHECKPOINT] Saved {i+1} results to {cp_path.resolve()}")

    return results

# -----------------------------
# Main
# -----------------------------
if __name__ == "__main__":
    if len(sys.argv) > 1:
        export_path = sys.argv[1]
    else:
        export_path = "/Users/devanshjain/Desktop/hackathon/forhackathon/conversations.json"

    print(f"Path to chat export JSON: {export_path}")

    chat_text = load_chat_text(export_path)
    print(f"DEBUG: Loaded {len(chat_text)} characters of chat text")

    chunks = chunk_text(chat_text, max_chars=8000)
    print(f"DEBUG: Split into {len(chunks)} chunks")

    results = asyncio.run(process_all_chunks(chunks))

    out_path = Path("analysis_results.json")
    with out_path.open("w") as f:
        json.dump(results, f, indent=2)

    print(f"Saved {len(results)} results to {out_path.resolve()}")
