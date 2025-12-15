#!/usr/bin/env python3
"""
Video Ingestion Service
Syncs videos from multiple sources (Google Drive, OneDrive, Local) to Hetzner Storage
"""

import os
import sys
import time
import json
import hashlib
import subprocess
from pathlib import Path
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor
import redis
from dotenv import load_dotenv

load_dotenv()

# Configuration
RCLONE_CONFIG = os.getenv('RCLONE_CONFIG_PATH', '/config/rclone.conf')
RAW_VIDEO_PATH = '/data/raw'
SYNC_INTERVAL = int(os.getenv('SYNC_INTERVAL', '3600'))  # 1 hour default

# Video extensions to sync
VIDEO_EXTENSIONS = {'.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.mpg', '.mpeg', '.m2ts', '.ts'}

# Database connection
def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('POSTGRES_HOST', 'postgres'),
        database=os.getenv('POSTGRES_DB', 'video_organizer'),
        user=os.getenv('POSTGRES_USER', 'videoorg'),
        password=os.getenv('POSTGRES_PASSWORD')
    )

# Redis connection
redis_client = redis.from_url(os.getenv('REDIS_URL', 'redis://redis:6379/0'))

def log(message, level='INFO'):
    timestamp = datetime.now().isoformat()
    print(f"[{timestamp}] [{level}] {message}", flush=True)

def calculate_file_hash(filepath):
    """Calculate xxHash of file for deduplication"""
    import xxhash
    h = xxhash.xxh64()
    try:
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                h.update(chunk)
        return h.hexdigest()
    except Exception as e:
        log(f"Error hashing {filepath}: {e}", 'ERROR')
        return None

def get_sync_sources():
    """Get enabled sync sources from database"""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT * FROM sync_sources 
                WHERE enabled = true 
                ORDER BY priority DESC
            """)
            return cur.fetchall()
    finally:
        conn.close()

def update_sync_status(source_id, files_synced, bytes_synced):
    """Update sync source statistics"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE sync_sources 
                SET last_sync = NOW(),
                    files_synced = files_synced + %s,
                    bytes_synced = bytes_synced + %s,
                    updated_at = NOW()
                WHERE id = %s
            """, (files_synced, bytes_synced, source_id))
            conn.commit()
    finally:
        conn.close()

def sync_from_source(source):
    """Sync videos from a single source using rclone"""
    source_name = source['source_name']
    source_path = source['source_path']
    source_type = source['source_type']
    
    log(f"Starting sync from {source_name} ({source_type})")
    
    # Build rclone command
    cmd = [
        'rclone', 'sync',
        source_path,
        RAW_VIDEO_PATH,
        '--config', RCLONE_CONFIG,
        '--include', '*.{' + ','.join([ext.lstrip('.') for ext in VIDEO_EXTENSIONS]) + '}',
        '--transfers', '4',
        '--checkers', '8',
        '--contimeout', '60s',
        '--timeout', '300s',
        '--retries', '3',
        '--low-level-retries', '10',
        '--stats', '1m',
        '--stats-one-line',
        '--verbose',
        '--progress',
        '--metadata',
        '--use-json-log'
    ]
    
    try:
        # Run rclone
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=7200  # 2 hour timeout
        )
        
        if result.returncode == 0:
            log(f"Sync completed successfully from {source_name}")
            
            # Parse stats from output
            files_synced = 0
            bytes_synced = 0
            
            # Scan for new files and add to database
            process_synced_files(source)
            
            # Update source stats
            update_sync_status(source['id'], files_synced, bytes_synced)
            
            return True
        else:
            log(f"Sync failed from {source_name}: {result.stderr}", 'ERROR')
            return False
            
    except subprocess.TimeoutExpired:
        log(f"Sync timeout for {source_name}", 'ERROR')
        return False
    except Exception as e:
        log(f"Sync error for {source_name}: {e}", 'ERROR')
        return False

def process_synced_files(source):
    """Process newly synced files and add to database"""
    conn = get_db_connection()
    raw_path = Path(RAW_VIDEO_PATH)
    
    log(f"Processing files from {source['source_name']}")
    
    for video_file in raw_path.rglob('*'):
        if not video_file.is_file():
            continue
            
        if video_file.suffix.lower() not in VIDEO_EXTENSIONS:
            continue
        
        try:
            # Calculate file hash for deduplication
            file_hash = calculate_file_hash(str(video_file))
            if not file_hash:
                continue
            
            # Get file info
            file_size = video_file.stat().st_size
            relative_path = str(video_file.relative_to(raw_path))
            
            # Check if already in database
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id FROM videos WHERE file_hash = %s
                """, (file_hash,))
                
                if cur.fetchone():
                    log(f"Skipping duplicate: {relative_path}")
                    continue
                
                # Insert new video
                cur.execute("""
                    INSERT INTO videos (
                        source_path, source_type, file_hash, 
                        file_size, status
                    ) VALUES (%s, %s, %s, %s, 'pending')
                    RETURNING id
                """, (
                    relative_path,
                    source['source_type'],
                    file_hash,
                    file_size
                ))
                
                video_id = cur.fetchone()[0]
                conn.commit()
                
                log(f"Added video {video_id}: {relative_path}")
                
                # Queue for analysis
                queue_for_analysis(video_id)
                
        except Exception as e:
            log(f"Error processing {video_file}: {e}", 'ERROR')
            conn.rollback()
    
    conn.close()

def queue_for_analysis(video_id):
    """Queue video for analysis"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO jobs (job_type, video_id, status, priority)
                VALUES ('analyze', %s, 'queued', 5)
            """, (video_id,))
            conn.commit()
            
        # Also push to Redis queue for immediate processing
        redis_client.lpush('analysis_queue', video_id)
        log(f"Queued video {video_id} for analysis")
        
    finally:
        conn.close()

def initialize_sync_sources():
    """Initialize default sync sources if none exist"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # Check if sources exist
            cur.execute("SELECT COUNT(*) FROM sync_sources")
            count = cur.fetchone()[0]
            
            if count == 0:
                log("Initializing default sync sources")
                
                # Add default sources
                sources = [
                    ('Google Drive', 'gdrive', 'gdrive:Videos', 10),
                    ('OneDrive', 'onedrive', 'onedrive:Videos', 9),
                    ('Local Storage', 'local', '/mnt/local', 8),
                ]
                
                for name, stype, path, priority in sources:
                    cur.execute("""
                        INSERT INTO sync_sources 
                        (source_name, source_type, source_path, priority)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT DO NOTHING
                    """, (name, stype, path, priority))
                
                conn.commit()
                log("Default sync sources initialized")
    finally:
        conn.close()

def main():
    log("Video Ingestion Service Starting...")
    
    # Ensure raw video directory exists
    Path(RAW_VIDEO_PATH).mkdir(parents=True, exist_ok=True)
    
    # Initialize sync sources
    initialize_sync_sources()
    
    # Main sync loop
    while True:
        try:
            sources = get_sync_sources()
            
            if not sources:
                log("No enabled sync sources found", 'WARNING')
            else:
                log(f"Found {len(sources)} sync sources")
                
                for source in sources:
                    try:
                        sync_from_source(source)
                    except Exception as e:
                        log(f"Error syncing {source['source_name']}: {e}", 'ERROR')
            
            log(f"Sync cycle complete. Sleeping for {SYNC_INTERVAL} seconds...")
            time.sleep(SYNC_INTERVAL)
            
        except KeyboardInterrupt:
            log("Shutting down...")
            break
        except Exception as e:
            log(f"Main loop error: {e}", 'ERROR')
            time.sleep(60)

if __name__ == '__main__':
    main()
