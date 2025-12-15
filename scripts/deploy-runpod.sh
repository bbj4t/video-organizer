#!/bin/bash

set -e

echo "======================================="
echo "RunPod Deployment Helper"
echo "======================================="
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

cd "$(dirname "$0")/../runpod"

echo -e "${YELLOW}This script will help you deploy the video analyzer to RunPod${NC}"
echo ""

# Check Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Docker is not installed${NC}"
    exit 1
fi

# Get Docker Hub username
read -p "Enter your Docker Hub username: " DOCKER_USER

if [ -z "$DOCKER_USER" ]; then
    echo -e "${RED}Docker Hub username required${NC}"
    exit 1
fi

IMAGE_NAME="$DOCKER_USER/video-analyzer"
IMAGE_TAG="latest"

echo ""
echo -e "${GREEN}Building Docker image...${NC}"
docker build -t $IMAGE_NAME:$IMAGE_TAG .

echo ""
echo -e "${GREEN}Logging in to Docker Hub...${NC}"
docker login

echo ""
echo -e "${GREEN}Pushing image to Docker Hub...${NC}"
docker push $IMAGE_NAME:$IMAGE_TAG

echo ""
echo "======================================="
echo -e "${GREEN}Image pushed successfully!${NC}"
echo "======================================="
echo ""
echo "Image: $IMAGE_NAME:$IMAGE_TAG"
echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo ""
echo "1. Go to RunPod dashboard: https://runpod.io"
echo ""
echo "2. For Serverless:"
echo "   - Navigate to 'Serverless'"
echo "   - Click 'New Endpoint'"
echo "   - Name: video-analyzer"
echo "   - Docker Image: $IMAGE_NAME:$IMAGE_TAG"
echo "   - GPU: RTX 4090 or better"
echo "   - Container Start Command: python -u handler.py"
echo "   - Click 'Deploy'"
echo "   - Copy the Endpoint ID"
echo "   - Add to .env: RUNPOD_ENDPOINT_ID=<endpoint-id>"
echo ""
echo "3. For Spot Pod:"
echo "   - Navigate to 'Pods'"
echo "   - Click 'Deploy'"
echo "   - GPU Type: RTX 4090"
echo "   - Deployment Type: Spot"
echo "   - Docker Image: $IMAGE_NAME:$IMAGE_TAG"
echo "   - Container Start Command: python -u handler.py"
echo "   - Expose HTTP Port: 8000"
echo "   - Click 'Deploy'"
echo "   - Copy the Pod ID"
echo "   - Add to .env: RUNPOD_POD_ID=<pod-id>"
echo ""
echo -e "${YELLOW}Recommended for cost efficiency:${NC}"
echo "Start with Serverless - only pay when analyzing"
echo "Switch to Spot Pod if processing large batches"
echo ""
echo -e "${GREEN}Cost estimates:${NC}"
echo "Serverless RTX 4090: ~\$0.0004/sec = \$1.44/hour"
echo "Spot RTX 4090: ~\$0.30/hour (70% savings)"
echo ""
