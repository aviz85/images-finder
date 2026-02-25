#!/usr/bin/env python3
"""
Search for images and open results with ~70% similarity match
"""

import sys
from pathlib import Path
import subprocess
import json

sys.path.insert(0, str(Path(__file__).parent))

from src.config import load_config
from src.search import ImageSearchEngine

def open_image_mac(image_path: Path):
    """Open image on macOS."""
    if not image_path.exists():
        print(f"  ⚠️  Image not found: {image_path}")
        return False
    
    try:
        subprocess.run(['open', str(image_path)], check=True)
        return True
    except Exception as e:
        print(f"  ❌ Error opening image: {e}")
        return False

def search_and_filter_70_percent(query: str, target_min: float = 0.65, target_max: float = 0.75, top_k: int = 100):
    """Search and filter results in 70% range."""
    print("=" * 70)
    print(f"  🔍 חיפוש: '{query}'")
    print("=" * 70)
    print()
    
    try:
        config = load_config(Path("config_optimized.yaml"))
        print("טוען מנוע חיפוש...")
        search_engine = ImageSearchEngine(config)
        search_engine.initialize()
        
        print(f"מחפש '{query}'... (top_k={top_k})")
        results = search_engine.search_by_text(query, top_k=top_k)
        
        if not results:
            print("❌ לא נמצאו תוצאות")
            return []
        
        print(f"✅ נמצאו {len(results)} תוצאות")
        print()
        
        # Show score distribution
        print("התפלגות ציוני התאמה:")
        score_ranges = {
            "90-100%": 0,
            "80-90%": 0,
            "70-80%": 0,
            "60-70%": 0,
            "50-60%": 0,
            "<50%": 0
        }
        
        for r in results:
            score_pct = r.score * 100
            if score_pct >= 90:
                score_ranges["90-100%"] += 1
            elif score_pct >= 80:
                score_ranges["80-90%"] += 1
            elif score_pct >= 70:
                score_ranges["70-80%"] += 1
            elif score_pct >= 60:
                score_ranges["60-70%"] += 1
            elif score_pct >= 50:
                score_ranges["50-60%"] += 1
            else:
                score_ranges["<50%"] += 1
        
        for range_name, count in score_ranges.items():
            if count > 0:
                print(f"  {range_name}: {count} תמונות")
        
        print()
        
        # Filter results in target range
        target_results = [
            r for r in results 
            if target_min <= r.score <= target_max
        ]
        
        print(f"תוצאות בטווח {target_min*100:.0f}-{target_max*100:.0f}%:")
        print(f"  נמצאו: {len(target_results)} תמונות")
        print()
        
        if target_results:
            # Show and open top 10 in range
            to_show = target_results[:10]
            
            print("פותח תמונות (עד 10 הראשונות):")
            print()
            
            opened_count = 0
            for i, result in enumerate(to_show, 1):
                score_percent = result.score * 100
                file_name = Path(result.file_path).name
                
                print(f"{i}. {file_name}")
                print(f"   התאמה: {score_percent:.1f}%")
                print(f"   נתיב: {result.file_path}")
                
                if open_image_mac(Path(result.file_path)):
                    opened_count += 1
                    print(f"   ✅ נפתח")
                print()
            
            print(f"✅ נפתחו {opened_count} תמונות")
            return target_results
        else:
            # Show closest to 70%
            print("לא נמצאו תוצאות בטווח המבוקש.")
            print("התמונות הקרובות ביותר ל-70%:")
            print()
            
            # Sort by distance from 0.7
            closest = sorted(results, key=lambda x: abs(x.score - 0.7))[:10]
            
            opened_count = 0
            for i, result in enumerate(closest, 1):
                score_percent = result.score * 100
                diff = abs(result.score - 0.7) * 100
                file_name = Path(result.file_path).name
                
                print(f"{i}. {file_name}")
                print(f"   התאמה: {score_percent:.1f}% (הפרש: {diff:.1f}%)")
                print(f"   נתיב: {result.file_path}")
                
                if open_image_mac(Path(result.file_path)):
                    opened_count += 1
                    print(f"   ✅ נפתח")
                print()
            
            print(f"✅ נפתחו {opened_count} תמונות")
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
        "cat",
        "sunset",
        "beach"
    ]
    
    print()
    print("=" * 70)
    print("  🧪 בדיקת חיפוש - תמונות עם ~70% התאמה")
    print("=" * 70)
    print()
    print("הערה: המערכת מחפשת רק מתוך התמונות שיש להן embeddings")
    print("כרגע יש רק 1,108 embeddings (מתוך 903K תמונות במסד הנתונים)")
    print()
    
    all_results = []
    
    for query in queries:
        try:
            results = search_and_filter_70_percent(
                query, 
                target_min=0.65, 
                target_max=0.75, 
                top_k=100
            )
            all_results.extend(results)
            
            print()
            input("לחץ Enter להמשך לשאילתה הבאה...")
            print()
            
        except KeyboardInterrupt:
            print("\n\n✅ המשתמש ביטל את החיפוש")
            break
        except Exception as e:
            print(f"❌ שגיאה בשאילתה '{query}': {e}")
            print()
    
    print()
    print("=" * 70)
    print(f"  ✅ סיום בדיקה")
    print("=" * 70)
    print(f"סה\"כ תוצאות בטווח 70%: {len(all_results)}")

if __name__ == '__main__':
    main()

