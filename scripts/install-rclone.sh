#!/bin/bash

set -e

echo "==============================="
echo "Rclone Configuration Helper"
echo "==============================="

# Color output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

CONFIG_DIR="$HOME/.config/rclone"
CONFIG_FILE="$CONFIG_DIR/rclone.conf"

mkdir -p $CONFIG_DIR

echo -e "${GREEN}This will help you configure your cloud storage sources${NC}"
echo

# Configure Google Drive
echo -e "${YELLOW}=== Configure Google Drive ===${NC}"
read -p "Do you want to configure Google Drive? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Starting Google Drive configuration..."
    echo "Follow the prompts to authenticate with Google"
    rclone config create gdrive drive scope=drive
    echo -e "${GREEN}Google Drive configured!${NC}"
fi

# Configure OneDrive
echo -e "${YELLOW}=== Configure Microsoft OneDrive ===${NC}"
read -p "Do you want to configure OneDrive? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Starting OneDrive configuration..."
    echo "Follow the prompts to authenticate with Microsoft"
    rclone config create onedrive onedrive
    echo -e "${GREEN}OneDrive configured!${NC}"
fi

# Test configurations
echo
echo -e "${GREEN}Testing configured remotes...${NC}"

if rclone listremotes | grep -q "gdrive:"; then
    echo "Testing Google Drive..."
    if rclone lsd gdrive: --max-depth 1; then
        echo -e "${GREEN}✓ Google Drive working${NC}"
    else
        echo -e "${YELLOW}⚠ Google Drive may need re-authentication${NC}"
    fi
fi

if rclone listremotes | grep -q "onedrive:"; then
    echo "Testing OneDrive..."
    if rclone lsd onedrive: --max-depth 1; then
        echo -e "${GREEN}✓ OneDrive working${NC}"
    else
        echo -e "${YELLOW}⚠ OneDrive may need re-authentication${NC}"
    fi
fi

# Copy config to project
echo
echo "Copying rclone config to project..."
cp $CONFIG_FILE ~/video-organizer/config/rclone.conf

echo
echo -e "${GREEN}Rclone configuration complete!${NC}"
echo
echo "Available remotes:"
rclone listremotes
echo
echo "Test your remotes with:"
echo "  rclone lsd gdrive:"
echo "  rclone lsd onedrive:"
