# 🔍 Semantic Search UI

UI פשוט לחיפוש סמנטי בתמונות עם יצירת thumbnails על הדרישה.

## התקנה

```bash
# התקן Flask (אם לא מותקן)
pip3 install flask

# או השתמש בסקריפט ההפעלה
./start_search_ui.sh
```

## הפעלה

```bash
./start_search_ui.sh
```

או ישירות:

```bash
python3 simple_search_ui.py
```

## שימוש

1. פתח דפדפן וגש ל: `http://localhost:5000`
2. הזן שאילתת חיפוש (לדוגמה: "שמיים", "אוקיינוס", "אנשים")
3. התוצאות יוצגו עם thumbnails
4. Thumbnails יווצרו אוטומטית על הדרישה ונשמרים על הדיסק החיצוני

## תכונות

- ✅ חיפוש סמנטי לפי טקסט (דרך FAISS)
- ✅ יצירת thumbnails על הדרישה
- ✅ שמירת thumbnails על הדיסק החיצוני (`/Volumes/My Book/.thumbnails/`)
- ✅ Thumbnails נשמרים ולא נמחקים - משמשים בחיפושים הבאים
- ✅ UI פשוט וידידותי בעברית

## מבנה הקבצים

- `simple_search_ui.py` - Flask server עם API endpoints
- `templates/search_ui.html` - Frontend UI
- `/Volumes/My Book/.thumbnails/` - תיקיית thumbnails על הדיסק החיצוני

## API Endpoints

- `POST /api/search` - חיפוש לפי טקסט
- `POST /api/generate-thumbnails` - יצירת thumbnails
- `GET /api/thumbnail/<hash>` - קבלת thumbnail
- `GET /api/check-thumbnail/<hash>` - בדיקה אם thumbnail קיים
- `POST /api/get-thumbnail-hash` - קבלת hash של thumbnail

