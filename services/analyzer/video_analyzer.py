#!/usr/bin/env python3
"""
Video Analyzer Service
Extracts frames, audio, and coordinates GPU analysis via RunPod
"""

import os
import sys
import time
import json
import subprocess
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
import psycopg2
from psycopg2.extras import RealDictCursor
import redis
from dotenv import load_dotenv
import ffmpeg
from PIL import Image
import io

from runpod_client import RunPodClient

load_dotenv()

# Configuration
RAW_VIDEO_PATH = '/data/raw'
ANALYZED_PATH = '/data/analyzed'
FRAME_EXTRACT_INTERVAL = int(os.getenv('FRAME_EXTRACT_INTERVAL', '30'))  # seconds
MAX_FRAMES = 10  # Maximum frames to analyze per video

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

class VideoAnalyzer:
    def __init__(self):
        self.runpod_client = RunPodClient()
    
    def extract_metadata(self, video_path: str) -> Dict:
        """Extract video metadata using ffprobe"""
        try:
            probe = ffmpeg.probe(video_path)
            
            video_stream = next(
                (s for s in probe['streams'] if s['codec_type'] == 'video'), 
                None
            )
            audio_stream = next(
                (s for s in probe['streams'] if s['codec_type'] == 'audio'),
                None
            )
            
            metadata = {
                'duration': float(probe['format'].get('duration', 0)),
                'size': int(probe['format'].get('size', 0)),
                'bitrate': int(probe['format'].get('bit_rate', 0)),
                'format': probe['format'].get('format_name', 'unknown')
            }
            
            if video_stream:
                metadata.update({
                    'width': video_stream.get('width', 0),
                    'height': video_stream.get('height', 0),
                    'codec': video_stream.get('codec_name', 'unknown'),
                    'fps': eval(video_stream.get('r_frame_rate', '0/1'))
                })
                metadata['resolution'] = f"{metadata['width']}x{metadata['height']}"
            
            if audio_stream:
                metadata.update({
                    'audio_codec': audio_stream.get('codec_name', 'unknown'),
                    'audio_channels': audio_stream.get('channels', 0),
                    'audio_sample_rate': audio_stream.get('sample_rate', 0)
                })
            
            return metadata
            
        except Exception as e:
            log(f"Error extracting metadata: {e}", 'ERROR')
            return {}
    
    def extract_frames(self, video_path: str, num_frames: int = MAX_FRAMES) -> List[bytes]:
        """Extract evenly spaced frames from video"""
        try:
            probe = ffmpeg.probe(video_path)
            duration = float(probe['format']['duration'])
            
            # Calculate frame timestamps
            interval = duration / (num_frames + 1)
            timestamps = [interval * (i + 1) for i in range(num_frames)]
            
            frames = []
            for ts in timestamps:
                try:
                    # Extract frame at timestamp
                    out, _ = (
                        ffmpeg
                        .input(video_path, ss=ts)
                        .filter('scale', 640, -1)  # Scale to 640px width
                        .output('pipe:', vframes=1, format='image2', vcodec='png')
                        .run(capture_stdout=True, capture_stderr=True)
                    )
                    frames.append(out)
                    
                except Exception as e:
                    log(f"Error extracting frame at {ts}s: {e}", 'WARNING')
                    continue
            
            log(f"Extracted {len(frames)} frames from video")
            return frames
            
        except Exception as e:
            log(f"Error in frame extraction: {e}", 'ERROR')
            return []
    
    def extract_audio(self, video_path: str) -> Optional[str]:
        """Extract audio to temporary file for transcription"""
        try:
            audio_path = f"/tmp/{Path(video_path).stem}_audio.wav"
            
            (
                ffmpeg
                .input(video_path)
                .output(audio_path, acodec='pcm_s16le', ac=1, ar='16000')
                .overwrite_output()
                .run(capture_stdout=True, capture_stderr=True)
            )
            
            log(f"Extracted audio to {audio_path}")
            return audio_path
            
        except Exception as e:
            log(f"Error extracting audio: {e}", 'ERROR')
            return None
    
    def analyze_video(self, video_id: int) -> bool:
        """Main video analysis workflow"""
        conn = get_db_connection()
        
        try:
            # Get video info
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT * FROM videos WHERE id = %s
                """, (video_id,))
                video = cur.fetchone()
            
            if not video:
                log(f"Video {video_id} not found", 'ERROR')
                return False
            
            video_path = Path(RAW_VIDEO_PATH) / video['source_path']
            
            if not video_path.exists():
                log(f"Video file not found: {video_path}", 'ERROR')
                return False
            
            log(f"Analyzing video {video_id}: {video['source_path']}")
            
            # Update status
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE videos SET status = 'analyzing' WHERE id = %s
                """, (video_id,))
                conn.commit()
            
            # Extract metadata
            log("Extracting metadata...")
            metadata = self.extract_metadata(str(video_path))
            
            # Update video with metadata
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE videos 
                    SET duration = %s, resolution = %s, codec = %s
                    WHERE id = %s
                """, (
                    metadata.get('duration'),
                    metadata.get('resolution'),
                    metadata.get('codec'),
                    video_id
                ))
                conn.commit()
            
            # Extract frames
            log("Extracting frames...")
            frames = self.extract_frames(str(video_path))
            
            if not frames:
                log("No frames extracted", 'ERROR')
                return False
            
            # Extract and transcribe audio
            log("Extracting audio...")
            audio_path = self.extract_audio(str(video_path))
            transcript = ""
            
            if audio_path:
                log("Transcribing audio...")
                transcript = self.runpod_client.transcribe_audio(audio_path)
                os.remove(audio_path)  # Clean up
            
            # Send to RunPod for analysis
            log("Sending to RunPod for GPU analysis...")
            analysis_result = self.runpod_client.analyze_video_frames(
                frames, 
                transcript,
                metadata
            )
            
            # Store analysis results
            self.store_analysis_results(video_id, analysis_result, transcript, conn)
            
            # Update status
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE videos SET status = 'analyzed' WHERE id = %s
                """, (video_id,))
                conn.commit()
            
            # Queue for organization
            self.queue_for_organization(video_id)
            
            log(f"Analysis complete for video {video_id}")
            return True
            
        except Exception as e:
            log(f"Error analyzing video {video_id}: {e}", 'ERROR')
            
            # Update status to error
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
    
    def store_analysis_results(
        self, 
        video_id: int, 
        analysis: Dict, 
        transcript: str,
        conn
    ):
        """Store analysis results in database"""
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO analysis_results (
                        video_id, content_type, detected_title, 
                        detected_year, detected_season, detected_episode,
                        confidence_score, ai_description, 
                        audio_language, scene_tags, analysis_metadata
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    video_id,
                    analysis.get('content_type'),
                    analysis.get('title'),
                    analysis.get('year'),
                    analysis.get('season'),
                    analysis.get('episode'),
                    analysis.get('confidence', 0),
                    analysis.get('description'),
                    analysis.get('language'),
                    analysis.get('tags', []),
                    json.dumps(analysis)
                ))
                conn.commit()
                
            log(f"Stored analysis results for video {video_id}")
            
        except Exception as e:
            log(f"Error storing analysis results: {e}", 'ERROR')
            conn.rollback()
    
    def queue_for_organization(self, video_id: int):
        """Queue video for organization"""
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO jobs (job_type, video_id, status, priority)
                    VALUES ('organize', %s, 'queued', 5)
                """, (video_id,))
                conn.commit()
            
            redis_client.lpush('organization_queue', video_id)
            log(f"Queued video {video_id} for organization")
            
        finally:
            conn.close()

def process_analysis_queue():
    """Main processing loop"""
    log("Video Analyzer Service Starting...")
    
    analyzer = VideoAnalyzer()
    
    # Ensure analyzed directory exists
    Path(ANALYZED_PATH).mkdir(parents=True, exist_ok=True)
    
    while True:
        try:
            # Check RunPod status
            if not analyzer.runpod_client.check_pod_status():
                log("RunPod not available, waiting...", 'WARNING')
                time.sleep(30)
                continue
            
            # Get next video from queue
            result = redis_client.brpop('analysis_queue', timeout=10)
            
            if result:
                _, video_id = result
                video_id = int(video_id)
                
                log(f"Processing video {video_id}")
                
                try:
                    analyzer.analyze_video(video_id)
                except Exception as e:
                    log(f"Analysis failed for video {video_id}: {e}", 'ERROR')
                    # Re-queue with delay
                    time.sleep(5)
                    redis_client.lpush('analysis_queue', video_id)
                    
        except KeyboardInterrupt:
            log("Shutting down...")
            break
        except Exception as e:
            log(f"Queue processing error: {e}", 'ERROR')
            time.sleep(5)

if __name__ == '__main__':
    process_analysis_queue()
