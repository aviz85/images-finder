#!/usr/bin/env python3
"""Simple live dashboard server using only built-in Python modules."""

import http.server
import socketserver
import json
import sqlite3
import os
from urllib.parse import urlparse, parse_qs
from datetime import datetime

PORT = 8888
DB_PATH = "/Users/aviz/images-finder/data/metadata.db"
TOTAL_TARGET = 3174680

class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    """Custom handler for the dashboard."""
    
    def do_GET(self):
        """Handle GET requests."""
        parsed = urlparse(self.path)
        
        if parsed.path == '/api/stats':
            self.serve_stats()
        elif parsed.path == '/' or parsed.path == '/dashboard':
            self.serve_dashboard()
        else:
            super().do_GET()
    
    def serve_stats(self):
        """Serve statistics as JSON."""
        try:
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            
            # Total registered images
            cur.execute('SELECT COUNT(*) FROM images')
            total = cur.fetchone()[0]
            
            # Images with embeddings
            cur.execute('SELECT COUNT(*) FROM images WHERE embedding_index IS NOT NULL')
            with_embeddings = cur.fetchone()[0]
            
            # Failed images
            cur.execute('SELECT COUNT(*) FROM failed_images')
            failed = cur.fetchone()[0]
            
            # SHA-256 hash progress
            cur.execute('SELECT COUNT(*) FROM images WHERE sha256_hash IS NOT NULL')
            with_sha256 = cur.fetchone()[0]
            
            # Perceptual hash progress  
            cur.execute('SELECT COUNT(*) FROM images WHERE perceptual_hash IS NOT NULL')
            with_phash = cur.fetchone()[0]
            
            # SHA-256 duplicates
            try:
                cur.execute('''
                    SELECT COUNT(*) FROM (
                        SELECT sha256_hash 
                        FROM images 
                        WHERE sha256_hash IS NOT NULL
                        GROUP BY sha256_hash 
                        HAVING COUNT(*) > 1
                    )
                ''')
                sha256_dup_groups = cur.fetchone()[0]
                
                cur.execute('''
                    SELECT SUM(cnt - 1) FROM (
                        SELECT COUNT(*) as cnt
                        FROM images 
                        WHERE sha256_hash IS NOT NULL
                        GROUP BY sha256_hash 
                        HAVING COUNT(*) > 1
                    )
                ''')
                sha256_duplicates = cur.fetchone()[0] or 0
            except:
                sha256_dup_groups = 0
                sha256_duplicates = 0
            
            # Perceptual duplicates
            try:
                cur.execute('''
                    SELECT COUNT(*) FROM (
                        SELECT perceptual_hash 
                        FROM images 
                        WHERE perceptual_hash IS NOT NULL
                        GROUP BY perceptual_hash 
                        HAVING COUNT(*) > 1
                    )
                ''')
                phash_dup_groups = cur.fetchone()[0]
                
                cur.execute('''
                    SELECT SUM(cnt - 1) FROM (
                        SELECT COUNT(*) as cnt
                        FROM images 
                        WHERE perceptual_hash IS NOT NULL
                        GROUP BY perceptual_hash 
                        HAVING COUNT(*) > 1
                    )
                ''')
                phash_duplicates = cur.fetchone()[0] or 0
            except:
                phash_dup_groups = 0
                phash_duplicates = 0
            
            # Recent images (last 5)
            cur.execute('''
                SELECT file_path, width, height 
                FROM images 
                ORDER BY id DESC 
                LIMIT 5
            ''')
            recent = cur.fetchall()
            
            conn.close()
            
            # Calculate percentages
            reg_percent = (total / TOTAL_TARGET * 100) if total > 0 else 0
            emb_percent = (with_embeddings / TOTAL_TARGET * 100) if with_embeddings > 0 else 0
            success_rate = ((total - failed) / total * 100) if total > 0 else 100
            sha256_percent = (with_sha256 / total * 100) if total > 0 else 0
            phash_percent = (with_phash / total * 100) if total > 0 else 0
            
            # Estimate time remaining (5.5 img/s average)
            remaining = TOTAL_TARGET - with_embeddings
            hours_remaining = remaining / (5.5 * 3600)
            days_remaining = hours_remaining / 24
            
            stats = {
                'timestamp': datetime.now().isoformat(),
                'total_target': TOTAL_TARGET,
                'registered': total,
                'with_embeddings': with_embeddings,
                'failed': failed,
                'with_sha256': with_sha256,
                'with_phash': with_phash,
                'reg_percent': round(reg_percent, 2),
                'emb_percent': round(emb_percent, 3),
                'success_rate': round(success_rate, 2),
                'sha256_percent': round(sha256_percent, 1),
                'phash_percent': round(phash_percent, 1),
                'sha256_duplicate_groups': sha256_dup_groups,
                'sha256_duplicates': sha256_duplicates,
                'phash_duplicate_groups': phash_dup_groups,
                'phash_duplicates': phash_duplicates,
                'days_remaining': round(days_remaining, 1),
                'hours_remaining': round(hours_remaining, 1),
                'recent_images': [
                    {
                        'name': os.path.basename(r[0]),
                        'size': f"{r[1]}x{r[2]}" if r[1] and r[2] else "unknown"
                    }
                    for r in recent
                ]
            }
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(stats).encode())
            
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            error = {'error': str(e)}
            self.wfile.write(json.dumps(error).encode())
    
    def serve_dashboard(self):
        """Serve the dashboard HTML."""
        html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Live Processing Dashboard - 3.17M Images</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: #333;
            padding: 20px;
            min-height: 100vh;
        }

        .container {
            max-width: 1400px;
            margin: 0 auto;
        }

        .header {
            text-align: center;
            color: white;
            margin-bottom: 30px;
            animation: fadeIn 0.5s;
        }

        .header h1 {
            font-size: 2.5rem;
            margin-bottom: 10px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.2);
        }

        .update-time {
            font-size: 0.9rem;
            opacity: 0.9;
            margin-top: 10px;
        }

        .pulse {
            display: inline-block;
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: #10b981;
            margin-right: 8px;
            animation: pulse 2s infinite;
        }

        @keyframes pulse {
            0%, 100% { opacity: 1; transform: scale(1); }
            50% { opacity: 0.5; transform: scale(1.1); }
        }

        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(-20px); }
            to { opacity: 1; transform: translateY(0); }
        }

        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }

        .stat-card {
            background: white;
            border-radius: 12px;
            padding: 25px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            transition: transform 0.3s;
            animation: fadeIn 0.5s;
        }

        .stat-card:hover {
            transform: translateY(-5px);
        }

        .stat-label {
            font-size: 0.85rem;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: #666;
            margin-bottom: 10px;
        }

        .stat-value {
            font-size: 2.5rem;
            font-weight: bold;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            margin-bottom: 5px;
        }

        .stat-subtitle {
            font-size: 0.9rem;
            color: #666;
        }

        .progress-section {
            background: white;
            border-radius: 12px;
            padding: 30px;
            margin-bottom: 20px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            animation: fadeIn 0.5s;
        }

        .progress-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
        }

        .progress-title {
            font-size: 1.2rem;
            font-weight: 600;
        }

        .progress-bar-container {
            background: #e0e0e0;
            border-radius: 10px;
            height: 40px;
            overflow: hidden;
            position: relative;
            margin-bottom: 10px;
        }

        .progress-bar {
            background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
            height: 100%;
            transition: width 1s ease;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: bold;
            font-size: 1.1rem;
        }

        .progress-details {
            display: flex;
            justify-content: space-between;
            font-size: 0.9rem;
            color: #666;
            margin-top: 10px;
        }

        .recent-images {
            background: white;
            border-radius: 12px;
            padding: 30px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            animation: fadeIn 0.5s;
        }

        .recent-title {
            font-size: 1.2rem;
            font-weight: 600;
            margin-bottom: 15px;
        }

        .image-item {
            background: #f8f9fa;
            padding: 12px 15px;
            margin: 8px 0;
            border-radius: 8px;
            border-left: 4px solid #667eea;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .image-name {
            font-weight: 500;
        }

        .image-size {
            color: #666;
            font-size: 0.9rem;
        }

        .error {
            background: #fee;
            color: #c00;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
        }

        .loading {
            text-align: center;
            padding: 40px;
            color: white;
            font-size: 1.2rem;
        }

        .spinner {
            border: 4px solid rgba(255,255,255,0.3);
            border-top: 4px solid white;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 0 auto 20px;
        }

        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🖼️ Live Processing Dashboard</h1>
            <p><span class="pulse"></span>Auto-updating every 10 seconds</p>
            <p class="update-time">Last updated: <span id="last-update">Never</span></p>
        </div>

        <div id="content">
            <div class="loading">
                <div class="spinner"></div>
                Loading data...
            </div>
        </div>
    </div>

    <script>
        let startTime = Date.now();

        function formatNumber(num) {
            return num.toLocaleString();
        }

        function formatDate(date) {
            return date.toLocaleString('en-US', { 
                month: 'short', 
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit'
            });
        }

        async function fetchStats() {
            try {
                const response = await fetch('/api/stats');
                if (!response.ok) throw new Error('Failed to fetch');
                return await response.json();
            } catch (error) {
                console.error('Error:', error);
                return null;
            }
        }

        function updateDashboard(stats) {
            if (!stats) {
                document.getElementById('content').innerHTML = `
                    <div class="error">
                        Failed to load data. Is the database accessible?
                    </div>
                `;
                return;
            }

            const embOfReg = stats.registered > 0 ? 
                ((stats.with_embeddings / stats.registered) * 100).toFixed(1) : 0;

            document.getElementById('content').innerHTML = `
                <div class="stats-grid">
                    <div class="stat-card">
                        <div class="stat-label">Total Target</div>
                        <div class="stat-value">${formatNumber(stats.total_target)}</div>
                        <div class="stat-subtitle">3.17 Million Images</div>
                    </div>
                    
                    <div class="stat-card">
                        <div class="stat-label">Registered</div>
                        <div class="stat-value">${formatNumber(stats.registered)}</div>
                        <div class="stat-subtitle">${stats.reg_percent}% complete</div>
                    </div>
                    
                    <div class="stat-card">
                        <div class="stat-label">With Embeddings</div>
                        <div class="stat-value">${formatNumber(stats.with_embeddings)}</div>
                        <div class="stat-subtitle">${stats.emb_percent}% of target</div>
                    </div>
                    
                    <div class="stat-card">
                        <div class="stat-label">Time Remaining</div>
                        <div class="stat-value">${stats.days_remaining}d</div>
                        <div class="stat-subtitle">${stats.hours_remaining} hours</div>
                    </div>
                </div>

                <div class="progress-section">
                    <div class="progress-header">
                        <div class="progress-title">📝 Registration Progress</div>
                        <div>${formatNumber(stats.registered)} / ${formatNumber(stats.total_target)}</div>
                    </div>
                    <div class="progress-bar-container">
                        <div class="progress-bar" style="width: ${Math.min(stats.reg_percent, 100)}%">
                            ${stats.reg_percent}%
                        </div>
                    </div>
                    <div class="progress-details">
                        <span>Success Rate: ${stats.success_rate}%</span>
                        <span>Failed: ${formatNumber(stats.failed)}</span>
                    </div>
                </div>

                <div class="progress-section">
                    <div class="progress-header">
                        <div class="progress-title">🧠 Embedding Generation</div>
                        <div>${formatNumber(stats.with_embeddings)} / ${formatNumber(stats.registered)}</div>
                    </div>
                    <div class="progress-bar-container">
                        <div class="progress-bar" style="width: ${embOfReg}%">
                            ${embOfReg}% of registered
                        </div>
                    </div>
                    <div class="progress-details">
                        <span>Speed: ~5.5 img/s (2 workers)</span>
                        <span>Overall: ${stats.emb_percent}% of target</span>
                    </div>
                </div>

                <div class="progress-section">
                    <div class="progress-header">
                        <div class="progress-title">🔍 Duplicate Detection</div>
                    </div>
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 15px;">
                        <div style="background: linear-gradient(135deg, #f093fb, #f5576c); padding: 15px; border-radius: 8px; color: white;">
                            <div style="font-size: 0.9rem; opacity: 0.9;">SHA-256 (Exact Copies)</div>
                            <div style="font-size: 1.5rem; font-weight: bold; margin: 5px 0;">${formatNumber(stats.with_sha256)}</div>
                            <div style="font-size: 0.85rem;">${stats.sha256_percent}% hashed</div>
                        </div>
                        <div style="background: linear-gradient(135deg, #4facfe, #00f2fe); padding: 15px; border-radius: 8px; color: white;">
                            <div style="font-size: 0.9rem; opacity: 0.9;">Perceptual (Visual)</div>
                            <div style="font-size: 1.5rem; font-weight: bold; margin: 5px 0;">${formatNumber(stats.with_phash)}</div>
                            <div style="font-size: 0.85rem;">${stats.phash_percent}% hashed</div>
                        </div>
                    </div>
                    <div class="progress-details" style="flex-direction: column; gap: 8px;">
                        <span>🔄 SHA-256 Duplicates: <strong>${formatNumber(stats.sha256_duplicates)}</strong> images in ${formatNumber(stats.sha256_duplicate_groups)} groups</span>
                        <span>🎨 Visual Duplicates: <strong>${formatNumber(stats.phash_duplicates)}</strong> images in ${formatNumber(stats.phash_duplicate_groups)} groups</span>
                    </div>
                </div>

                <div class="recent-images">
                    <div class="recent-title">📸 Recently Registered</div>
                    ${stats.recent_images.map(img => `
                        <div class="image-item">
                            <span class="image-name">${img.name}</span>
                            <span class="image-size">${img.size}</span>
                        </div>
                    `).join('')}
                </div>
            `;

            document.getElementById('last-update').textContent = formatDate(new Date());
        }

        async function refresh() {
            const stats = await fetchStats();
            updateDashboard(stats);
        }

        // Initial load
        refresh();

        // Auto-refresh every 10 seconds
        setInterval(refresh, 10000);
    </script>
</body>
</html>"""
        
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(html.encode())
    
    def log_message(self, format, *args):
        """Override to reduce log spam."""
        pass

if __name__ == '__main__':
    print("=" * 60)
    print("  🖼️  LIVE PROCESSING DASHBOARD")
    print("=" * 60)
    print("")
    print("✓ Starting server...")
    print("")
    print("📊 Dashboard URL:")
    print(f"   http://localhost:{PORT}")
    print("")
    print("💡 Open this URL in your browser to see live progress!")
    print("")
    print("🔄 Auto-refreshes every 10 seconds")
    print("⌨️  Press Ctrl+C to stop")
    print("")
    print("=" * 60)
    print("")
    
    with socketserver.TCPServer(("", PORT), DashboardHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n\n✓ Server stopped")

