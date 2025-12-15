#!/usr/bin/env python3
"""
Jellyfin Organizer Service
Matches videos to TMDB/TVDB and organizes them with proper naming
"""

import os
import sys
import time
import shutil
from pathlib import Path
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor
import redis
from dotenv import load_dotenv

from tmdb_matcher import TMDBMatcher
from naming import JellyfinNamer

load_dotenv()

# Paths
RAW_VIDEO_PATH = '/data/raw'
ANALYZED_PATH = '/data/analyzed'
ORGANIZED_PATH = '/data/organized'

redis_client = redis.from_url(os.getenv('REDIS_URL', 'redis://redis:6379/0'))

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv('POSTGRES_HOST', 'postgres'),
        database=os.getenv('POSTGRES_DB', 'video_organizer'),
        user=os.getenv('POSTGRES_USER', 'videoorg'),
        password=os.getenv('POSTGRES_PASSWORD')
    )

def log(message, level='INFO'):
    timestamp = datetime.now().isoformat()
    print(f"[{timestamp}] [{level}] {message}", flush=True)

class VideoOrganizer:
    def __init__(self):
        self.matcher = TMDBMatcher()
        self.namer = JellyfinNamer()
    
    def organize_video(self, video_id: int) -> bool:
        """
        Main organization workflow
        1. Get analysis results
        2. Match to TMDB/TVDB
        3. Generate Jellyfin path
        4. Copy/move file
        5. Create NFO
        """
        conn = get_db_connection()
        
        try:
            # Get video and analysis
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT v.*, a.* 
                    FROM videos v
                    LEFT JOIN analysis_results a ON v.id = a.video_id
                    WHERE v.id = %s
                """, (video_id,))
                video = cur.fetchone()
            
            if not video:
                log(f"Video {video_id} not found", 'ERROR')
                return False
            
            log(f"Organizing video {video_id}: {video['source_path']}")
            
            # Update status
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE videos SET status = 'organizing' WHERE id = %s
                """, (video_id,))
                conn.commit()
            
            # Check if already has a match
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT * FROM media_matches WHERE video_id = %s
                    ORDER BY match_confidence DESC LIMIT 1
                """, (video_id,))
                existing_match = cur.fetchone()
            
            if existing_match:
                log(f"Using existing match: {existing_match['title']}")
                match = dict(existing_match)
            else:
                # Try to match
                log("Matching to TMDB...")
                match = self.matcher.auto_match(video)
                
                if not match:
                    log("No match found, using original filename", 'WARNING')
                    # Use original name in "Other" category
                    match = {
                        'media_type': 'unknown',
                        'title': Path(video['source_path']).stem,
                        'confidence': 0
                    }
                else:
                    # Store match in database
                    self.store_match(video_id, match, conn)
            
            # Generate target path
            source_path = Path(RAW_VIDEO_PATH) / video['source_path']
            extension = source_path.suffix
            
            target_path = self.namer.generate_path(match, extension)
            target_path = Path(ORGANIZED_PATH) / target_path.lstrip('/')
            
            log(f"Target path: {target_path}")
            
            # Create directory
            target_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Copy file
            log(f"Copying file...")
            shutil.copy2(source_path, target_path)
            
            # Create NFO file
            if match.get('media_type') in ['movie', 'tv']:
                log("Creating NFO file...")
                self.namer.create_nfo_file(match, str(target_path))
            
            # Store organized file info
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO organized_files (
                        video_id, jellyfin_path, hetzner_path, file_size
                    ) VALUES (%s, %s, %s, %s)
                """, (
                    video_id,
                    str(target_path.relative_to(ORGANIZED_PATH)),
                    str(target_path),  # Will sync to Hetzner
                    target_path.stat().st_size
                ))
                conn.commit()
            
            # Update video status
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE videos SET status = 'organized' WHERE id = %s
                """, (video_id,))
                conn.commit()
            
            log(f"Successfully organized video {video_id}")
            
            # Queue for Hetzner upload
            self.queue_for_upload(video_id, str(target_path))
            
            return True
            
        except Exception as e:
            log(f"Error organizing video {video_id}: {e}", 'ERROR')
            
            try:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE videos SET status = 'error' WHERE id = %s
                    """, (video_id,))
                    conn.commit()
            except:
                pass
            
            return False
            
        finally:
            conn.close()
    
    def store_match(self, video_id: int, match: Dict, conn):
        """Store TMDB match in database"""
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO media_matches (
                        video_id, media_type, tmdb_id, tvdb_id,
                        title, year, season, episode, episode_title,
                        match_confidence, metadata
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    video_id,
                    match.get('media_type'),
                    match.get('tmdb_id'),
                    match.get('tvdb_id'),
                    match.get('title'),
                    match.get('year'),
                    match.get('season'),
                    match.get('episode'),
                    match.get('episode_title'),
                    match.get('confidence', 0),
                    json.dumps(match)
                ))
                conn.commit()
                
            log(f"Stored match for video {video_id}")
            
        except Exception as e:
            log(f"Error storing match: {e}", 'ERROR')
            conn.rollback()
    
    def queue_for_upload(self, video_id: int, local_path: str):
        """Queue organized file for upload to Hetzner"""
        redis_client.lpush('upload_queue', json.dumps({
            'video_id': video_id,
            'local_path': local_path
        }))
        log(f"Queued video {video_id} for Hetzner upload")

def process_organization_queue():
    """Main processing loop"""
    log("Jellyfin Organizer Service Starting...")
    
    organizer = VideoOrganizer()
    
    # Ensure organized directory exists
    Path(ORGANIZED_PATH).mkdir(parents=True, exist_ok=True)
    
    while True:
        try:
            # Get next video from queue
            result = redis_client.brpop('organization_queue', timeout=10)
            
            if result:
                _, video_id = result
                video_id = int(video_id)
                
                log(f"Processing video {video_id}")
                
                try:
                    organizer.organize_video(video_id)
                except Exception as e:
                    log(f"Organization failed for video {video_id}: {e}", 'ERROR')
                    time.sleep(5)
                    
        except KeyboardInterrupt:
            log("Shutting down...")
            break
        except Exception as e:
            log(f"Queue processing error: {e}", 'ERROR')
            time.sleep(5)

if __name__ == '__main__':
    import json
    process_organization_queue()
