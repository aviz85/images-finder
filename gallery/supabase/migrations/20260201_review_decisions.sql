CREATE TABLE IF NOT EXISTS review_decisions (
    id SERIAL PRIMARY KEY,
    image_id INTEGER NOT NULL UNIQUE,
    decision TEXT NOT NULL,
    original_path TEXT,
    reviewed_at TIMESTAMP DEFAULT NOW()
);

ALTER TABLE review_decisions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "public_access" ON review_decisions FOR ALL USING (true) WITH CHECK (true);
