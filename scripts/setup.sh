#!/bin/bash

set -e

echo "==================================="
echo "Video Organizer Setup - Hetzner VM"
echo "==================================="

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   echo -e "${RED}This script should NOT be run as root${NC}" 
   echo "Run as your regular user, sudo will be used when needed"
   exit 1
fi

# Update system
echo -e "${GREEN}Updating system packages...${NC}"
sudo apt-get update
sudo apt-get upgrade -y

# Install dependencies
echo -e "${GREEN}Installing dependencies...${NC}"
sudo apt-get install -y \
    curl \
    wget \
    git \
    unzip \
    jq \
    python3 \
    python3-pip \
    python3-venv \
    docker.io \
    docker-compose \
    fuse3 \
    nfs-common \
    sshfs

# Add user to docker group
echo -e "${GREEN}Adding user to docker group...${NC}"
sudo usermod -aG docker $USER

# Install rclone
echo -e "${GREEN}Installing rclone...${NC}"
curl https://rclone.org/install.sh | sudo bash

# Create directory structure
echo -e "${GREEN}Creating directory structure...${NC}"
mkdir -p ~/video-organizer
mkdir -p ~/video-organizer/local_media
mkdir -p ~/video-organizer/config
mkdir -p ~/video-organizer/logs
mkdir -p /mnt/hetzner-storage

# Copy project files
cd ~/video-organizer

# Create environment file
if [ ! -f .env ]; then
    echo -e "${YELLOW}Creating .env file...${NC}"
    cp .env.example .env
    echo -e "${YELLOW}Please edit .env file with your credentials${NC}"
fi

# Setup rclone config
echo -e "${GREEN}Setting up rclone...${NC}"
echo -e "${YELLOW}You'll need to configure cloud sources interactively${NC}"
read -p "Do you want to configure rclone now? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    ./scripts/install-rclone.sh
fi

# Mount Hetzner Storage Box
echo -e "${GREEN}Setting up Hetzner Storage Box mount...${NC}"
read -p "Enter your Hetzner Storage Box host (e.g., u123456.your-storagebox.de): " STORAGE_HOST
read -p "Enter your Hetzner Storage Box username: " STORAGE_USER
read -sp "Enter your Hetzner Storage Box password: " STORAGE_PASS
echo

# Create mount point
sudo mkdir -p /mnt/hetzner-storage

# Add to fstab for persistent mount
if ! grep -q "hetzner-storage" /etc/fstab; then
    echo "${STORAGE_USER}@${STORAGE_HOST}:/ /mnt/hetzner-storage fuse.sshfs delay_connect,_netdev,user,idmap=user,transform_symlinks,identityfile=/home/$USER/.ssh/id_rsa,allow_other,default_permissions,uid=$(id -u),gid=$(id -g) 0 0" | sudo tee -a /etc/fstab
fi

# Generate SSH key if not exists
if [ ! -f ~/.ssh/id_rsa ]; then
    echo -e "${GREEN}Generating SSH key...${NC}"
    ssh-keygen -t rsa -b 4096 -f ~/.ssh/id_rsa -N ""
fi

# Upload SSH key to Storage Box
echo -e "${GREEN}Uploading SSH key to Hetzner Storage Box...${NC}"
echo -e "${YELLOW}You may need to enter your password${NC}"
cat ~/.ssh/id_rsa.pub | ssh ${STORAGE_USER}@${STORAGE_HOST} "mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys"

# Mount Storage Box
sudo mount /mnt/hetzner-storage

# Install RunPod SDK
echo -e "${GREEN}Installing RunPod SDK...${NC}"
pip3 install runpod

# Create systemd service for auto-start
echo -e "${GREEN}Creating systemd service...${NC}"
cat > /tmp/video-organizer.service <<EOF
[Unit]
Description=Video Organizer
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/home/$USER/video-organizer
ExecStart=/usr/bin/docker-compose up -d
ExecStop=/usr/bin/docker-compose down
User=$USER

[Install]
WantedBy=multi-user.target
EOF

sudo mv /tmp/video-organizer.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable video-organizer.service

# Setup database
echo -e "${GREEN}Initializing database...${NC}"
docker-compose up -d postgres redis
sleep 5

# Build and start services
echo -e "${GREEN}Building Docker images...${NC}"
docker-compose build

echo -e "${GREEN}Starting services...${NC}"
docker-compose up -d

# Show status
echo -e "${GREEN}==================================="
echo "Setup Complete!"
echo "===================================${NC}"
echo
echo "Services running:"
docker-compose ps
echo
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Edit .env file with your API keys:"
echo "   nano .env"
echo "2. Configure rclone for cloud sources:"
echo "   rclone config"
echo "3. View logs:"
echo "   docker-compose logs -f"
echo "4. Access web dashboard:"
echo "   http://$(curl -s ifconfig.me):8080"
echo
echo -e "${YELLOW}To start/stop:${NC}"
echo "   docker-compose up -d"
echo "   docker-compose down"
echo
echo -e "${RED}IMPORTANT:${NC} You may need to log out and back in for docker group membership to take effect"
