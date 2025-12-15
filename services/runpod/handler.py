#!/usr/bin/env python3
"""
RunPod Handler - Runs on GPU pod for video analysis
Uses LLaVA-Video, Whisper, and other models for analysis
"""

import os
import base64
import json
from io import BytesIO
from typing import List, Dict
import torch
from PIL import Image
import runpod

# Import models
from transformers import (
    AutoProcessor, 
    AutoModelForVision2Seq,
    WhisperProcessor,
    WhisperForConditionalGeneration,
    pipeline
)

print("Loading models...", flush=True)

# Device
device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"Using device: {device}", flush=True)

# Load LLaVA-Video for frame analysis
# You can swap this for other vision models
try:
    vision_model_name = "llava-hf/llava-v1.6-mistral-7b-hf"
    vision_processor = AutoProcessor.from_pretrained(vision_model_name)
    vision_model = AutoModelForVision2Seq.from_pretrained(
        vision_model_name,
        torch_dtype=torch.float16 if device == "cuda" else torch.float32,
        device_map="auto" if device == "cuda" else None
    )
    print("Vision model loaded", flush=True)
except Exception as e:
    print(f"Error loading vision model: {e}", flush=True)
    vision_model = None
    vision_processor = None

# Load Whisper for audio transcription
try:
    whisper_model_name = "openai/whisper-large-v3"
    whisper_processor = WhisperProcessor.from_pretrained(whisper_model_name)
    whisper_model = WhisperForConditionalGeneration.from_pretrained(
        whisper_model_name,
        torch_dtype=torch.float16 if device == "cuda" else torch.float32,
        device_map="auto" if device == "cuda" else None
    )
    print("Whisper model loaded", flush=True)
except Exception as e:
    print(f"Error loading Whisper: {e}", flush=True)
    whisper_model = None
    whisper_processor = None

print("Models loaded successfully", flush=True)

def analyze_frames(frame_images: List[bytes], metadata: Dict) -> Dict:
    """
    Analyze video frames to determine content
    """
    if not vision_model or not vision_processor:
        return {
            "error": "Vision model not loaded",
            "content_type": "unknown"
        }
    
    try:
        # Decode images
        images = []
        for frame_data in frame_images[:5]:  # Analyze first 5 frames
            img = Image.open(BytesIO(base64.b64decode(frame_data)))
            images.append(img)
        
        # Analyze with LLaVA
        prompt = """Analyze these video frames and provide:
1. Content type (movie, tv_episode, documentary, music_video, or other)
2. Title or description
3. Year (if identifiable)
4. For TV: Season and episode number (if visible)
5. Genre/tags
6. Brief description

Respond in JSON format with keys: content_type, title, year, season, episode, tags, description, confidence
"""
        
        # Process images
        inputs = vision_processor(
            text=prompt,
            images=images,
            return_tensors="pt"
        ).to(device)
        
        # Generate analysis
        with torch.no_grad():
            output = vision_model.generate(
                **inputs,
                max_new_tokens=500,
                do_sample=False
            )
        
        # Decode output
        result_text = vision_processor.decode(output[0], skip_special_tokens=True)
        
        # Try to parse JSON from response
        try:
            # Extract JSON from response
            start_idx = result_text.find('{')
            end_idx = result_text.rfind('}') + 1
            if start_idx != -1 and end_idx != 0:
                result_json = json.loads(result_text[start_idx:end_idx])
            else:
                # Fallback parsing
                result_json = parse_fallback_response(result_text)
        except:
            result_json = parse_fallback_response(result_text)
        
        return result_json
        
    except Exception as e:
        print(f"Frame analysis error: {e}", flush=True)
        return {
            "error": str(e),
            "content_type": "unknown"
        }

def parse_fallback_response(text: str) -> Dict:
    """Parse non-JSON response into structured format"""
    result = {
        "content_type": "unknown",
        "title": "",
        "year": None,
        "season": None,
        "episode": None,
        "tags": [],
        "description": text[:500],
        "confidence": 0.5
    }
    
    # Simple keyword detection
    text_lower = text.lower()
    
    if "movie" in text_lower:
        result["content_type"] = "movie"
    elif any(x in text_lower for x in ["episode", "season", "tv show", "series"]):
        result["content_type"] = "tv_episode"
    elif "documentary" in text_lower:
        result["content_type"] = "documentary"
    
    return result

def transcribe_audio(audio_data: str) -> Dict:
    """
    Transcribe audio using Whisper
    """
    if not whisper_model or not whisper_processor:
        return {
            "error": "Whisper model not loaded",
            "text": ""
        }
    
    try:
        # Decode audio
        import soundfile as sf
        import io
        
        audio_bytes = base64.b64decode(audio_data)
        audio_array, sample_rate = sf.read(io.BytesIO(audio_bytes))
        
        # Process with Whisper
        inputs = whisper_processor(
            audio_array,
            sampling_rate=sample_rate,
            return_tensors="pt"
        ).to(device)
        
        # Generate transcription
        with torch.no_grad():
            predicted_ids = whisper_model.generate(**inputs)
        
        # Decode transcription
        transcription = whisper_processor.batch_decode(
            predicted_ids, 
            skip_special_tokens=True
        )[0]
        
        return {
            "text": transcription,
            "language": "auto"  # Could detect language from output
        }
        
    except Exception as e:
        print(f"Transcription error: {e}", flush=True)
        return {
            "error": str(e),
            "text": ""
        }

def handler(event):
    """
    Main RunPod handler function
    """
    try:
        input_data = event.get("input", {})
        task = input_data.get("task", "video_analysis")
        
        if task == "video_analysis":
            # Video frame analysis
            frames = input_data.get("frames", [])
            transcript = input_data.get("transcript", "")
            metadata = input_data.get("metadata", {})
            
            if not frames:
                return {"error": "No frames provided"}
            
            # Analyze frames
            analysis = analyze_frames(frames, metadata)
            
            # Enhance with transcript if available
            if transcript:
                analysis["transcript"] = transcript
                # Could use transcript to refine analysis
            
            return analysis
            
        elif task == "transcribe":
            # Audio transcription
            audio_data = input_data.get("audio", "")
            
            if not audio_data:
                return {"error": "No audio data provided"}
            
            result = transcribe_audio(audio_data)
            return result
            
        else:
            return {"error": f"Unknown task: {task}"}
            
    except Exception as e:
        print(f"Handler error: {e}", flush=True)
        return {"error": str(e)}

# Start RunPod serverless
if __name__ == "__main__":
    print("Starting RunPod handler...", flush=True)
    runpod.serverless.start({"handler": handler})
