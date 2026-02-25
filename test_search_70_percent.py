#!/usr/bin/env python3
"""
Test search queries and open results with ~70% similarity
"""

import sys
from pathlib import Path
import subprocess
import webbrowser
from typing import List

sys.path.insert(0, str(Path(__file__).parent))

from src.config import load_config
from src.search import ImageSearchEngine

def open_image(image_path: Path):
    """Open image on macOS."""
    if not image_path.exists():
        print(f"⚠️  Image not found: {image_path}")
        return False
    
    try:
        # macOS command to open image
        subprocess.run(['open', str(image_path)], check=True)
        return True
    except Exception as e:
        print(f"❌ Error opening image: {e}")
        return False

def search_and_show(query: str, target_score_range: tuple = (0.65, 0.75), top_k: int = 50):
    """Search and show results around target score range."""
    print("=" * 60)
    print(f"  🔍 חיפוש: '{query}'")
    print("=" * 60)
    print()
    
    try:
        # Load config
        config = load_config(Path("config_optimized.yaml"))
        
        # Initialize search engine
        print("טוען מנוע חיפוש...")
        search_engine = ImageSearchEngine(config)
        search_engine.initialize()
        
        # Search
        print(f"מחפש '{query}'...")
        results = search_engine.search_by_text(query, top_k=top_k)
        
        if not results:
            print("❌ לא נמצאו תוצאות")
            return []
        
        print(f"✅ נמצאו {len(results)} תוצאות")
        print()
        
        # Filter results in target score range
        target_results = [
            r for r in results 
            if target_score_range[0] <= r.score <= target_score_range[1]
        ]
        
        print(f"תוצאות עם התאמה {target_score_range[0]*100:.0f}-{target_score_range[1]*100:.0f}%:")
        print(f"  נמצאו: {len(target_results)} תוצאות")
        print()
        
        if target_results:
            # Show top 5 in range
            to_show = target_results[:5]
            
            for i, result in enumerate(to_show, 1):
                score_percent = result.score * 100
                print(f"{i}. {Path(result.file_path).name}")
                print(f"   התאמה: {score_percent:.1f}%")
                print(f"   נתיב: {result.file_path}")
                print()
            
            # Ask which to open
            print("פותח את התמונות...")
            for result in to_show:
                open_image(Path(result.file_path))
            
            return target_results
        else:
            # Show closest results
            print("לא נמצאו תוצאות בטווח המבוקש.")
            print("התמונות הקרובות ביותר:")
            print()
            
            closest = sorted(results, key=lambda x: abs(x.score - 0.7), reverse=False)[:5]
            
            for i, result in enumerate(closest, 1):
                score_percent = result.score * 100
                diff = abs(result.score - 0.7) * 100
                print(f"{i}. {Path(result.file_path).name}")
                print(f"   התאמה: {score_percent:.1f}% (הפרש: {diff:.1f}%)")
                print(f"   נתיב: {result.file_path}")
                print()
            
            return closest
        
    except Exception as e:
        print(f"❌ שגיאה: {e}")
        import traceback
        traceback.print_exc()
        return []

def main():
    # Test queries
    queries = [
        "sky",
        "ocean water",
        "mountain landscape",
        "people smiling",
        "cat"
    ]
    
    print()
    print("=" * 60)
    print("  🧪 בדיקת חיפוש - תמונות עם ~70% התאמה")
    print("=" * 60)
    print()
    
    all_results = []
    
    for query in queries:
        try:
            results = search_and_show(query, target_score_range=(0.65, 0.75), top_k=50)
            all_results.extend(results)
            
            print()
            input("לחץ Enter להמשך לשאילתה הבאה...")
            print()
            
        except KeyboardInterrupt:
            print("\n\nהמשתמש ביטל את החיפוש")
            break
        except Exception as e:
            print(f"❌ שגיאה בשאילתה '{query}': {e}")
            print()
    
    print()
    print("=" * 60)
    print(f"  ✅ סיום בדיקה")
    print("=" * 60)
    print(f"סה\"כ תוצאות: {len(all_results)}")

if __name__ == '__main__':
    main()

