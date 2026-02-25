#!/usr/bin/env python3
"""
Open search results visually - creates HTML viewer with images.
"""

import requests
import json
from pathlib import Path
import urllib.parse

BASE_URL = "http://localhost:8000"

def create_html_viewer(queries):
    """Create HTML page showing search results."""
    
    html = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Search Results Viewer</title>
    <style>
        * { box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            margin: 0;
            padding: 20px;
            background: #f0f0f0;
        }
        .header {
            background: white;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        h1 { margin: 0 0 10px 0; color: #333; }
        .query-section {
            background: white;
            padding: 20px;
            margin-bottom: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .query-title {
            font-size: 24px;
            font-weight: bold;
            color: #2c3e50;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 3px solid #3498db;
        }
        .results-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
            gap: 20px;
        }
        .result-card {
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            overflow: hidden;
            transition: transform 0.2s, box-shadow 0.2s;
            background: white;
        }
        .result-card:hover {
            transform: translateY(-4px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        }
        .image-container {
            width: 100%;
            height: 300px;
            background: #f5f5f5;
            display: flex;
            align-items: center;
            justify-content: center;
            position: relative;
            overflow: hidden;
        }
        .result-image {
            max-width: 100%;
            max-height: 100%;
            object-fit: contain;
            cursor: pointer;
        }
        .result-info {
            padding: 15px;
        }
        .score {
            display: inline-block;
            background: #3498db;
            color: white;
            padding: 5px 12px;
            border-radius: 20px;
            font-weight: bold;
            font-size: 14px;
            margin-bottom: 8px;
        }
        .file-name {
            font-weight: bold;
            color: #2c3e50;
            margin: 8px 0;
            word-break: break-word;
        }
        .file-path {
            font-size: 11px;
            color: #7f8c8d;
            word-break: break-all;
            margin-top: 5px;
        }
        .no-image {
            color: #95a5a6;
            text-align: center;
            padding: 40px;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🔍 Search Results Viewer</h1>
        <p>Visual results for queries: """ + ", ".join(f'"{q}"' for q in queries) + """</p>
    </div>
"""
    
    for query in queries:
        try:
            response = requests.get(
                f"{BASE_URL}/search/text",
                params={"q": query, "top_k": 10},
                timeout=30
            )
            
            if response.status_code != 200:
                continue
            
            data = response.json()
            results = data.get("results", [])
            
            html += f"""
    <div class="query-section">
        <div class="query-title">Query: "{query}" ({len(results)} results)</div>
        <div class="results-grid">
"""
            
            for result in results:
                file_path = result.get("file_path", "")
                file_name = result.get("file_name", "")
                score = result.get("score", 0)
                score_percent = score * 100
                
                # Use file:// URL for local images
                file_url = f"file://{urllib.parse.quote(file_path, safe='')}"
                
                # Get folder name
                folder = Path(file_path).parent.name if file_path else ""
                
                html += f"""
            <div class="result-card">
                <div class="image-container">
                    <img src="{file_url}" 
                         alt="{file_name}" 
                         class="result-image"
                         onclick="window.open('{file_url}', '_blank')"
                         onerror="this.style.display='none'; this.parentElement.innerHTML='<div class=\\"no-image\\">Image not accessible<br/>Path: {file_name}</div>'">
                </div>
                <div class="result-info">
                    <div class="score">{score_percent:.2f}% Match</div>
                    <div class="file-name">{file_name}</div>
                    <div class="file-path">{folder}</div>
                </div>
            </div>
"""
            
            html += """
        </div>
    </div>
"""
            
        except Exception as e:
            html += f"""
    <div class="query-section">
        <div class="query-title">Query: "{query}"</div>
        <p style="color: red;">Error: {e}</p>
    </div>
"""
    
    html += """
</body>
</html>
"""
    
    return html

if __name__ == "__main__":
    queries = ["protest", "crowd", "signs", "men"]
    
    print("Creating HTML viewer with search results...")
    html = create_html_viewer(queries)
    
    output_path = Path("/Users/aviz/images-finder/search_results.html")
    output_path.write_text(html, encoding='utf-8')
    
    print(f"✅ Created: {output_path}")
    print("Opening in browser...")
    
    import subprocess
    subprocess.run(["open", str(output_path)])


