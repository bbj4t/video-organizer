FROM runpod/pytorch:2.1.0-py3.10-cuda11.8.0-devel-ubuntu22.04

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download models (optional - for faster cold starts)
# Uncomment to bake models into image
# RUN python -c "from transformers import AutoProcessor, AutoModelForVision2Seq; \
#     AutoProcessor.from_pretrained('llava-hf/llava-v1.6-mistral-7b-hf'); \
#     AutoModelForVision2Seq.from_pretrained('llava-hf/llava-v1.6-mistral-7b-hf')"

# Copy handler
COPY handler.py .

# Start handler
CMD ["python", "-u", "handler.py"]
