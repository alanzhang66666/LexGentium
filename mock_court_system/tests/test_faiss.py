import faiss
import os
import numpy as np

index_path = "database/legal_articles.index"
abs_path = os.path.abspath(index_path)

print(f"Testing relative path: {index_path}")
try:
    index = faiss.read_index(index_path)
    print("Success with relative path")
except Exception as e:
    print(f"Failed with relative path: {e}")

print(f"Testing absolute path: {abs_path}")
try:
    index = faiss.read_index(abs_path)
    print("Success with absolute path")
except Exception as e:
    print(f"Failed with absolute path: {e}")




