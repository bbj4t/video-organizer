#!/bin/bash

set -e

# Video Organizer - Quick Deploy Script
# Run this on your Hetzner VM after git clone

echo "======================================="
echo "Video Organizer - Quick Deploy"
echo "======================================="
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Check for root
if [[ $EUID -eq 0 ]]; then
    echo -e "${RED}Don't run as root. Run as your regular user.${NC}"
    exit 1
fi

echo -e "${GREEN}Step 1: System Update${NC}"
sudo apt-get update && sudo apt-get upgrade -y

echo ""
echo -e "${GREEN}Step 2: Install Docker${NC}"
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker $USER
    rm get-docker.sh
    echo -e "${YELLOW}Docker installed. You may need to log out and back in.${NC}"
else
    echo "Docker already installed"
fi

echo ""
echo -e "${GREEN}Step 3: Install Docker Compose${NC}"
if ! command -v docker-compose &> /dev/null; then
    sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
else
    echo "Docker Compose already installed"
fi

echo ""
echo -e "${GREEN}Step 4: Install Rclone${NC}"
if ! command -v rclone &> /dev/null; then
    curl https://rclone.org/install.sh | sudo bash
else
    echo "Rclone already installed"
fi

echo ""
echo -e "${GREEN}Step 5: Create directories${NC}"
mkdir -p ~/video-organizer/local_media
mkdir -p ~/video-organizer/logs

echo ""
echo -e "${GREEN}Step 6: Configure Environment${NC}"

if [ ! -f .env ]; then
    cp .env.example .env
    
    echo ""
    echo -e "${YELLOW}Please provide the following information:${NC}"
    echo ""
    
    # Hetzner Storage Box
    read -p "Hetzner Storage Box host: " STORAGE_HOST
    read -p "Hetzner Storage Box username: " STORAGE_USER
    read -sp "Hetzner Storage Box password: " STORAGE_PASS
    echo ""
    
    # RunPod
    read -p "RunPod API Key: " RUNPOD_KEY
    read -p "RunPod Endpoint ID (or leave blank for spot pod): " RUNPOD_ENDPOINT
    
    # TMDB
    read -p "TMDB API Key: " TMDB_KEY
    
    # Update .env file
    sed -i "s/HETZNER_STORAGE_HOST=.*/HETZNER_STORAGE_HOST=$STORAGE_HOST/" .env
    sed -i "s/HETZNER_STORAGE_USER=.*/HETZNER_STORAGE_USER=$STORAGE_USER/" .env
    sed -i "s/HETZNER_STORAGE_PASSWORD=.*/HETZNER_STORAGE_PASSWORD=$STORAGE_PASS/" .env
    sed -i "s/RUNPOD_API_KEY=.*/RUNPOD_API_KEY=$RUNPOD_KEY/" .env
    sed -i "s/RUNPOD_ENDPOINT_ID=.*/RUNPOD_ENDPOINT_ID=$RUNPOD_ENDPOINT/" .env
    sed -i "s/TMDB_API_KEY=.*/TMDB_API_KEY=$TMDB_KEY/" .env
    
    echo -e "${GREEN}Environment configured${NC}"
else
    echo ".env file already exists"
fi

echo ""
echo -e "${GREEN}Step 7: Setup Hetzner Storage Box${NC}"

# Generate SSH key if not exists
if [ ! -f ~/.ssh/id_rsa ]; then
    ssh-keygen -t rsa -b 4096 -f ~/.ssh/id_rsa -N ""
fi

# Create mount point
sudo mkdir -p /mnt/hetzner-storage

# Add to fstab
if ! grep -q "hetzner-storage" /etc/fstab; then
    STORAGE_USER=$(grep HETZNER_STORAGE_USER .env | cut -d '=' -f2)
    STORAGE_HOST=$(grep HETZNER_STORAGE_HOST .env | cut -d '=' -f2)
    
    echo "$STORAGE_USER@$STORAGE_HOST:/ /mnt/hetzner-storage fuse.sshfs delay_connect,_netdev,user,idmap=user,transform_symlinks,identityfile=$HOME/.ssh/id_rsa,allow_other,default_permissions,uid=$(id -u),gid=$(id -g) 0 0" | sudo tee -a /etc/fstab
fi

echo ""
echo -e "${YELLOW}Uploading SSH key to Hetzner Storage Box...${NC}"
echo -e "${YELLOW}You'll need to enter your password once:${NC}"

STORAGE_USER=$(grep HETZNER_STORAGE_USER .env | cut -d '=' -f2)
STORAGE_HOST=$(grep HETZNER_STORAGE_HOST .env | cut -d '=' -f2)

cat ~/.ssh/id_rsa.pub | ssh ${STORAGE_USER}@${STORAGE_HOST} "mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys"

# Mount
sudo mount /mnt/hetzner-storage || echo "Mount may already exist"

echo ""
echo -e "${GREEN}Step 8: Configure Rclone${NC}"
echo -e "${YELLOW}Do you want to configure cloud sources now? (Google Drive, OneDrive)${NC}"
read -p "(y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    chmod +x scripts/install-rclone.sh
    ./scripts/install-rclone.sh
fi

echo ""
echo -e "${GREEN}Step 9: Make scripts executable${NC}"
chmod +x scripts/*.sh

echo ""
echo -e "${GREEN}Step 10: Build Docker images${NC}"
docker-compose build

echo ""
echo -e "${GREEN}Step 11: Start services${NC}"
docker-compose up -d

echo ""
echo -e "${GREEN}Step 12: Initialize database${NC}"
sleep 10  # Wait for postgres to start
docker-compose exec -T postgres psql -U videoorg -d video_organizer < sql/init.sql || echo "Database may already be initialized"

echo ""
echo -e "${GREEN}Step 13: Create systemd service${NC}"
cat > /tmp/video-organizer.service <<EOF
[Unit]
Description=Video Organizer
Requires=docker.service
After=docker.service network-online.target
Wants=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=$PWD
ExecStart=/usr/local/bin/docker-compose up -d
ExecStop=/usr/local/bin/docker-compose down
User=$USER
Environment="PATH=/usr/local/bin:/usr/bin:/bin"

[Install]
WantedBy=multi-user.target
EOF

sudo mv /tmp/video-organizer.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable video-organizer.service

echo ""
echo "======================================="
echo -e "${GREEN}Deployment Complete!${NC}"
echo "======================================="
echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo ""
echo "1. Check service status:"
echo "   docker-compose ps"
echo ""
echo "2. View logs:"
echo "   docker-compose logs -f"
echo ""
echo "3. Access web dashboard:"
echo "   http://$(curl -s ifconfig.me):8080"
echo ""
echo "4. Add local media to:"
echo "   $PWD/local_media/"
echo ""
echo "5. Check Hetzner Storage Box mount:"
echo "   ls -la /mnt/hetzner-storage"
echo ""
echo -e "${YELLOW}To manage services:${NC}"
echo "   docker-compose up -d     # Start"
echo "   docker-compose down      # Stop"
echo "   docker-compose restart   # Restart"
echo "   docker-compose logs -f   # View logs"
echo ""
echo -e "${YELLOW}RunPod Setup (if using serverless):${NC}"
echo "   cd runpod"
echo "   docker build -t yourusername/video-analyzer:latest ."
echo "   docker push yourusername/video-analyzer:latest"
echo "   # Then create endpoint in RunPod dashboard"
echo ""
echo -e "${RED}Important:${NC}"
echo "If you installed Docker for the first time, log out and back in"
echo "for group permissions to take effect."
echo ""
