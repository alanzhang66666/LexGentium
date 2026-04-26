import os
import sys
import traceback

# Add current directory to sys.path to ensure imports work
sys.path.append(os.getcwd())

from core.law_retriever import LawRetriever, get_dashscope_api_key

# Sample text (Third party findings from CI-1)
sample_text = """
一、借款人：吴xx。
二、借款期限、金额及用途：2023年5月6日借款6000元，到期日为2025年4月26日，用于购买手机数码产品；2023年5月6日借款20000元，到期日为2026年4月26日，用于购买家具家居产品；2023年8月14日借款10000元，到期日为2025年8月26日，用于购买家用电器。
三、约定利率：日利率0.045%，折合年化利率为16.425%；发生逾期的，从逾期之日起，对逾期贷款本金按合同约定利率水平上加收50%计收逾期罚息，不能按时支付的利息，按逾期罚息利率计收复利。
四、还款方式：等额本息还款。
五、尚欠本息：因合同约定逾期罚息标准已超过年利率24%，招联xx公司主张以未归还本金为基数自借款逾期之日起以年利率24%计算罚息。
"""

import sqlite3
import numpy as np

def inspect_db():
    db_path = "database/legal_articles.db"
    print(f"Inspecting {db_path}...")
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        print(f"Tables: {tables}")
        
        # Check columns in 'laws' (assuming table name from previous code)
        # Or check the first table found
        if tables:
            # Check count
            cursor.execute(f"SELECT COUNT(*) FROM articles")
            count = cursor.fetchone()[0]
            print(f"Total articles: {count}")
                
    except Exception as e:
        print(f"DB Error: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

def test_retrieval():
    print("Initializing LawRetriever...")
    # Use relative paths to avoid encoding issues with Faiss on Windows
    # Ensure these paths are correct relative to where the script is run
    db_path = "database/legal_articles.db"
    index_path = "database/legal_articles.index"
    mapping_path = "database/legal_articles_id_map.npy"
    api_key = get_dashscope_api_key()

    try:
        retriever = LawRetriever(
            db_path=db_path,
            index_path=index_path,
            mapping_path=mapping_path,
            api_key=api_key
        )
        print("LawRetriever initialized.")
        print(f"Index dimension: {retriever.index.d}")
        
        print(f"\nSearching for text:\n{sample_text.strip()}...")
        results = retriever.search(sample_text, top_k=3)
        
        print(f"\nFound {len(results)} results:")
        for i, res in enumerate(results):
            print(f"\n--- Result {i+1} (Score: {res['score']:.4f}) ---")
            print(f"Law ID: {res['law_id']}")
            print(f"Content: {res['content']}")
            
    except Exception as e:
        print(f"Error: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    # inspect_db()
    test_retrieval()




