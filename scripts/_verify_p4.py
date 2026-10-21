import sqlite_vec, sqlite3, requests, time, struct

print("=== sqlite-vec ===")
conn = sqlite3.connect(":memory:")
conn.enable_load_extension(True)
sqlite_vec.load(conn)
conn.enable_load_extension(False)
print("sqlite_vec.__version__ =", sqlite_vec.__version__)

# Create a table with vec0 virtual table — nomic-embed-text default dim = 768
conn.execute("CREATE VIRTUAL TABLE test_vec USING vec0(embedding float[768])")
emb_list = [0.1] * 768
emb_bytes = struct.pack(f"{len(emb_list)}f", *emb_list)
conn.execute("INSERT INTO test_vec(rowid, embedding) VALUES (?, ?)", (1, emb_bytes))
r = conn.execute("SELECT rowid, distance FROM test_vec WHERE embedding MATCH ? ORDER BY distance LIMIT 1", (emb_bytes,)).fetchone()
print("vec0 virtual table query result (rowid, distance):", r)
conn.close()
print("sqlite-vec: OK")

print("\n=== Ollama embedding ===")
t0 = time.time()
r = requests.post(
    "http://127.0.0.1:11434/api/embeddings",
    json={"model": "nomic-embed-text", "prompt": "hello world test"},
    timeout=60,
)
dt = time.time() - t0
print(f"status={r.status_code}  latency={dt:.2f}s")
if r.status_code == 200:
    emb = r.json()["embedding"]
    print(f"dim={len(emb)}  sample={emb[:5]}")
    assert len(emb) == 768, f"expected 768, got {len(emb)}"
    print("Ollama embedding: OK (768-dim)")
else:
    print("ERROR:", r.text[:300])
