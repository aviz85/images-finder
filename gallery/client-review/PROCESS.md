# תהליך המשך עבודה - Village Gallery Selection

## סיכום מצב נוכחי

### מספרים
- **אושרו:** 121 תמונות (verified)
- **נדחו:** 43 תמונות
- **נותרו לסקירה:** ~1,600 תמונות
- **הערכה לתמונות טובות:** 370-500

### קבצים
```
gallery/client-review/
├── README.md              # הסבר ללקוח
├── PROCESS.md            # מסמך זה
├── approved_ids.txt      # IDs שאושרו (121)
├── rejected_ids.txt      # IDs שנדחו (43)
├── review_gallery.html   # דף סקירה ללקוח
└── data/
    ├── classification.db      # תוצאות סיווג
    ├── embeddings.db          # מיפוי IDs
    └── gallery_embeddings.npy # וקטורים (22MB)
```

## תהליך ההמשך

### שלב 1: לקוח מסמן תמונות
1. לקוח פותח `review_gallery.html`
2. מסמן ירוק/אדום
3. מעתיק את הרשימות ושולח לך

### שלב 2: עדכון הנתונים
```python
# הוסף IDs חדשים לקבצים
# approved_ids.txt - ירוקים חדשים
# rejected_ids.txt - אדומים חדשים
```

### שלב 3: הרצת חיפוש משופר
```bash
cd /Users/aviz/images-finder
source venv/bin/activate
python gallery/client-review/scripts/find_similar.py
```

### שלב 4: יצירת גלריה סופית
```bash
python gallery/client-review/scripts/create_final_gallery.py
```

## סקריפט Python להמשך

```python
#!/usr/bin/env python3
"""
find_similar.py - Find more similar images based on updated seeds
"""
import sqlite3
import numpy as np
from pathlib import Path

BASE = Path('/Users/aviz/images-finder/gallery/client-review')

# Load approved/rejected
def load_ids(filename):
    text = (BASE / filename).read_text()
    # Extract numbers from text
    import re
    return set(int(x) for x in re.findall(r'\d+', text))

approved = load_ids('approved_ids.txt')
rejected = load_ids('rejected_ids.txt')

print(f"Approved: {len(approved)}")
print(f"Rejected: {len(rejected)}")

# Load embeddings
embeddings = np.load(BASE / 'data/gallery_embeddings.npy')

conn = sqlite3.connect(str(BASE / 'data/embeddings.db'))
rows = conn.execute("SELECT id, embedding_idx FROM embedding_progress").fetchall()
conn.close()

id_to_idx = {r[0]: r[1] for r in rows}
idx_to_id = {r[1]: r[0] for r in rows}

# Get centroids
good_idx = [id_to_idx[i] for i in approved if i in id_to_idx]
bad_idx = [id_to_idx[i] for i in rejected if i in id_to_idx]

good_centroid = embeddings[good_idx].mean(axis=0)
good_centroid /= np.linalg.norm(good_centroid)

bad_centroid = embeddings[bad_idx].mean(axis=0)
bad_centroid /= np.linalg.norm(bad_centroid)

# Score all
norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
emb_norm = embeddings / norms

good_sim = emb_norm @ good_centroid
bad_sim = emb_norm @ bad_centroid
scores = good_sim - 0.7 * bad_sim

# Find best
exclude = approved | rejected
for idx in np.argsort(scores)[::-1][:100]:
    img_id = idx_to_id[idx]
    if img_id not in exclude:
        print(f"ID: {img_id}, Score: {scores[idx]:.3f}")
```

## הערות טכניות

### למה 121 תמונות מספיקות כ-seeds?
- מייצגות מגוון של ישובים
- נבחרו ידנית ע"י המשתמש
- מאפשרות למצוא דומים דרך embedding similarity

### למה לא להשתמש רק ב-CLIP classification?
- CLIP מסווג "landscape" גם לנוף בלי ישוב
- הסיווג הידני מדויק יותר לדרישה הספציפית
- השילוב: CLIP לסינון ראשוני + ידני לדיוק

### Embedding Quality
- נוצרו מחדש ספציפית ל-11,724 תמונות
- ViT-B-32 (512 dimensions)
- קובץ נקי, 1:1 עם התמונות
