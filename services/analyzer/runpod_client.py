#!/usr/bin/env python3
"""
RunPod Client - Handles video analysis using GPU on RunPod
Supports both serverless and spot pods
"""

import os
import time
import json
import base64
import requests
from datetime import datetime
from typing import List, Dict, Optional
import runpod

class RunPodClient:
    def __init__(self):
        self.api_key = os.getenv('RUNPOD_API_KEY')
        self.endpoint_id = os.getenv('RUNPOD_ENDPOINT_ID')  # For serverless
        self.pod_id = os.getenv('RUNPOD_POD_ID')  # For spot pods
        self.use_serverless = bool(self.endpoint_id)
        
        if not self.api_key:
            raise ValueError("RUNPOD_API_KEY not set")
        
        runpod.api_key = self.api_key
        
        self.log("RunPod client initialized", 
                f"Mode: {'Serverless' if self.use_serverless else 'Spot Pod'}")
    
    def log(self, message, detail=''):
        timestamp = datetime.now().isoformat()
        print(f"[{timestamp}] [RunPodClient] {message} {detail}", flush=True)
    
    def analyze_video_frames(
        self, 
        frame_images: List[bytes], 
        audio_transcript: str = "",
        metadata: Dict = {}
    ) -> Dict:
        """
        Send video frames to RunPod for analysis
        
        Args:
            frame_images: List of frame images as bytes
            audio_transcript: Transcribed audio text
            metadata: Video metadata (duration, resolution, etc.)
        
        Returns:
            Analysis results
        """
        # Encode frames to base64
        encoded_frames = [
            base64.b64encode(frame).decode('utf-8') 
            for frame in frame_images
        ]
        
        payload = {
            "input": {
                "frames": encoded_frames,
                "transcript": audio_transcript,
                "metadata": metadata,
                "task": "video_analysis"
            }
        }
        
        if self.use_serverless:
            return self._run_serverless(payload)
        else:
            return self._run_spot_pod(payload)
    
    def _run_serverless(self, payload: Dict) -> Dict:
        """Run analysis on serverless endpoint"""
        self.log("Submitting to serverless endpoint", self.endpoint_id)
        
        try:
            endpoint = runpod.Endpoint(self.endpoint_id)
            
            # Run the job
            run_request = endpoint.run(payload)
            
            # Wait for completion
            self.log("Waiting for results...")
            result = run_request.output(timeout=300)  # 5 min timeout
            
            if result:
                self.log("Analysis complete")
                return result
            else:
                raise Exception("No result returned from serverless endpoint")
                
        except Exception as e:
            self.log(f"Serverless error: {e}", 'ERROR')
            raise
    
    def _run_spot_pod(self, payload: Dict) -> Dict:
        """Run analysis on spot pod via HTTP"""
        self.log("Submitting to spot pod", self.pod_id)
        
        try:
            # Get pod info to get the endpoint
            pod = runpod.get_pod(self.pod_id)
            
            if not pod:
                raise Exception(f"Pod {self.pod_id} not found")
            
            # Construct endpoint URL
            # Assuming the pod is running a web service
            pod_url = f"https://{self.pod_id}-8000.proxy.runpod.net/analyze"
            
            # Send request
            response = requests.post(
                pod_url,
                json=payload,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                timeout=300
            )
            
            response.raise_for_status()
            result = response.json()
            
            self.log("Analysis complete")
            return result
            
        except Exception as e:
            self.log(f"Spot pod error: {e}", 'ERROR')
            raise
    
    def transcribe_audio(self, audio_file_path: str) -> str:
        """
        Transcribe audio using Whisper on RunPod
        
        Args:
            audio_file_path: Path to audio file
        
        Returns:
            Transcribed text
        """
        self.log(f"Transcribing audio: {audio_file_path}")
        
        # Read audio file
        with open(audio_file_path, 'rb') as f:
            audio_data = base64.b64encode(f.read()).decode('utf-8')
        
        payload = {
            "input": {
                "audio": audio_data,
                "task": "transcribe",
                "language": "auto"  # Auto-detect language
            }
        }
        
        try:
            if self.use_serverless:
                result = self._run_serverless(payload)
            else:
                result = self._run_spot_pod(payload)
            
            return result.get('text', '')
            
        except Exception as e:
            self.log(f"Transcription error: {e}", 'ERROR')
            return ""
    
    def check_pod_status(self) -> bool:
        """Check if pod is running and healthy"""
        if not self.pod_id:
            return True  # Serverless is always available
        
        try:
            pod = runpod.get_pod(self.pod_id)
            if pod and pod.get('status') == 'running':
                return True
            return False
        except Exception as e:
            self.log(f"Pod status check error: {e}", 'ERROR')
            return False
    
    def get_cost_estimate(self, frame_count: int, duration: float) -> float:
        """
        Estimate cost for analyzing a video
        
        Args:
            frame_count: Number of frames to analyze
            duration: Video duration in seconds
        
        Returns:
            Estimated cost in USD
        """
        if self.use_serverless:
            # Serverless pricing (example: $0.0002 per second)
            compute_time = (frame_count * 2) + (duration / 60 * 5)  # rough estimate
            cost = compute_time * 0.0002
        else:
            # Spot pod pricing (example: $0.20/hour for RTX 4090)
            estimated_minutes = (frame_count / 10) + 1  # rough estimate
            cost = (estimated_minutes / 60) * 0.20
        
        return round(cost, 4)
