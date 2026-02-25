# 🔍 Debugging: למה CLIP נתקע?

## הבעיה

חיפוש טקסט נתקע על "Step 1: Encoding text query to embedding..."
המודל CLIP המקומי לא עובד כמו שצריך.

## למה זה קורה?

### 1. **המודל לא נטען בזמן הפעלת השרת**
- המודל אמור להיטען ב-`initialize()` שמופעל ב-startup
- אבל אם יש שגיאה בטעינה, היא לא נראית
- המודל נשאר `None` ואז נתקע כשמנסים להשתמש בו

### 2. **encode_text איטי מאוד בפעם הראשונה**
- PyTorch עושה JIT compilation בפעם הראשונה
- על CPU זה יכול לקחת 30-60 שניות
- נראה כמו "תקוע" אבל למעשה זה עובד לאט

### 3. **בעיית זיכרון/משאבים**
- המודל דורש הרבה RAM
- אם אין מספיק זיכרון, זה נתקע
- CPU של M1 יכול להיות איטי עם מודלים גדולים

### 4. **המודל נטען אבל encode_text נכשל**
- אולי יש בעיה בטוקניזציה
- או שהמודל לא תומך בטקסט (רק תמונות)
- או שיש בעיה בהתקנה

## איך לבדוק?

### בדיקה 1: האם המודל נטען?
```python
# ב-server.py, אחרי initialize()
if search_engine.embedding_model is None:
    print("❌ MODEL NOT LOADED!")
else:
    print("✅ Model loaded")
```

### בדיקה 2: נסה לקודד טקסט ישירות
```python
from src.embeddings import EmbeddingModel
model = EmbeddingModel(model_name="ViT-B-32", pretrained="openai", device="cpu")
embedding = model.encode_text("test")
print("✅ Text encoding works!")
```

### בדיקה 3: בדוק את הלוגים
הלוגים צריכים להראות:
1. "Loading model..." 
2. "Model loaded. Embedding dimension: 512"
3. "encode_text: Starting encoding..."
4. "encode_text: Tokenizing text..."
5. "encode_text: Generating embeddings..."
6. "encode_text: Complete!"

אם זה נעצר באמצע, שם הבעיה.

## פתרונות

### פתרון 1: וודא שהמודל נטען ב-startup
```python
# ב-server.py, אחרי initialize()
if search_engine.embedding_model is None:
    logger.error("MODEL NOT LOADED! This will cause hanging.")
    raise RuntimeError("Embedding model failed to load")
```

### פתרון 2: הוסף timeout
```python
import signal

def timeout_handler(signum, frame):
    raise TimeoutError("Text encoding took too long")

signal.signal(signal.SIGALRM, timeout_handler)
signal.alarm(30)  # 30 seconds timeout
try:
    embedding = model.encode_text(query)
finally:
    signal.alarm(0)
```

### פתרון 3: טען מודל קל יותר
במקום ViT-B-32, נסה מודל קטן יותר:
- ViT-B-16 (מהיר יותר)
- ViT-SO400M (יותר קל)

### פתרון 4: השתמש ב-Gemini API
כמו שכבר הוספנו - Gemini API מהיר ואין בעיית טעינה.

## מה לעשות עכשיו?

1. **בדוק את הלוגים של השרת** - איפה זה נעצר?
2. **נסה לקודד טקסט ישירות** - האם זה עובד?
3. **בדוק את הזיכרון** - האם יש מספיק RAM?
4. **אם זה עדיין נתקע** - השתמש ב-Gemini API כמו שהגדרנו


