import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.law_retriever import LawRetriever, get_dashscope_api_key

def test_retrieval():
    print("Testing LawRetriever with new database...")
    
    db_dir = project_root / "database"
    db_path = str(db_dir / "legal_articles.db")
    index_path = str(db_dir / "legal_articles.index")
    mapping_path = str(db_dir / "legal_articles_id_map.npy")
    
    api_key = get_dashscope_api_key()
    
    try:
        retriever = LawRetriever(
            db_path=db_path,
            index_path=index_path,
            mapping_path=mapping_path,
            api_key=api_key
        )
        print("✅ LawRetriever initialized successfully.")
        print(f"Index Dimension: {retriever.index.d}")
        
        test_queries = [
            "借款合同纠纷，利息计算",
            "故意伤害罪的量刑标准",
            "离婚诉讼中财产分割原则",
            "专利侵权赔偿数额的确定",
            "合同违约责任的承担方式"
        ]

        for query in test_queries:
            print(f"\n{'='*50}")
            print(f"Searching for: {query}")
            print(f"{'='*50}")
            
            results = retriever.search(query, top_k=3)
            
            if results:
                for i, res in enumerate(results):
                    print(f"\nResult {i+1}:")
                    print(f"  Law: {res.get('law_name', 'N/A')}")
                    print(f"  Article: {res.get('article_number', 'N/A')}")
                    content = res.get('content', '')
                    print(f"  Content: {content[:100]}..." if len(content) > 100 else f"  Content: {content}")
                    print(f"  Score: {res.get('score', 'N/A')}")
            else:
                print("⚠️ No results found.")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_retrieval()




