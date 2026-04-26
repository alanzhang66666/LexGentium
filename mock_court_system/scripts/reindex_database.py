import sqlite3
import numpy as np
import faiss
import dashscope
from dashscope import TextEmbedding
import os
import time

# Configuration
# Paths relative to project root (assuming script is run from project root)
DB_PATH = "database/legal_articles.db"
NEW_INDEX_PATH = "database/legal_articles.index"
NEW_MAPPING_PATH = "database/legal_articles_id_map.npy"
API_KEY = "sk-tkfnlkgyhkxihqqgyowdrkhdpzyldhtblrjdmnqmthmfjqln"

dashscope.api_key = API_KEY

def get_embedding(text):
    try:
        resp = TextEmbedding.call(
            model=TextEmbedding.Models.text_embedding_v2,
            input=text
        )
        if resp.status_code == 200:
            return resp.output["embeddings"][0]["embedding"]
        else:
            print(f"Error getting embedding: {resp}")
            return None
    except Exception as e:
        print(f"Exception: {e}")
        return None

def main():
    print(f"Connecting to {DB_PATH}...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Fetch all articles
    cursor.execute("SELECT id, content FROM articles")
    rows = cursor.fetchall()
    print(f"Found {len(rows)} articles.")
    
    ids = []
    embeddings = []
    
    for i, (article_id, content) in enumerate(rows):
        print(f"Processing {i+1}/{len(rows)}: ID {article_id}")
        emb = get_embedding(content)
        if emb:
            embeddings.append(emb)
            ids.append(article_id)
        else:
            print(f"Skipping ID {article_id} due to embedding failure.")
        
        # Rate limit
        time.sleep(0.1)
        
    if not embeddings:
        print("No embeddings generated.")
        return

    # Convert to numpy array
    emb_matrix = np.array(embeddings, dtype=np.float32)
    print(f"Embedding matrix shape: {emb_matrix.shape}")
    
    # Create Faiss index
    d = emb_matrix.shape[1] # Should be 1536
    index = faiss.IndexFlatL2(d)
    index.add(emb_matrix)
    print(f"Index contains {index.ntotal} vectors.")
    
    # Save index
    faiss.write_index(index, NEW_INDEX_PATH)
    print(f"Saved index to {NEW_INDEX_PATH}")
    
    # Save mapping
    # The index 0 corresponds to ids[0], index 1 to ids[1], etc.
    # We save the list of IDs as the mapping.
    mapping_arr = np.array(ids)
    np.save(NEW_MAPPING_PATH, mapping_arr)
    print(f"Saved mapping to {NEW_MAPPING_PATH}")
    
    conn.close()

if __name__ == "__main__":
    main()
