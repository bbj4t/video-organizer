# Video Organizer for Jellyfin

Automated video library consolidation and organization system using Hetzner storage, RunPod GPU inference, and Jellyfin naming conventions.

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Cloud Sources  │────▶│  Hetzner VM      │────▶│  RunPod GPU     │
│  - Google Drive │     │  - Ingestion     │     │  - LLaVA        │
│  - OneDrive     │     │  - Analysis      │     │  - Whisper      │
│  - Local        │     │  - Organization  │     │  - Analysis     │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                               │
                               ▼
                        ┌──────────────────┐
                        │  Hetzner Storage │
                        │  - Organized     │
                        │  - Jellyfin      │
                        └──────────────────┘
```

## Features

- **Multi-source sync**: Google Drive, OneDrive, local storage
- **GPU-accelerated analysis**: RunPod serverless or spot pods
- **AI-powered categorization**: LLaVA-Video for content identification
- **Audio transcription**: Whisper for dialogue analysis
- **TMDB matching**: Automatic movie/TV show identification
- **Jellyfin naming**: Perfect compatibility with Jellyfin libraries
- **Deduplication**: File hash-based duplicate detection
- **Web dashboard**: Monitor progress and manage library

## Prerequisites

### Accounts Required
1. **Hetzner Cloud**: VM + Storage Box
2. **RunPod**: For GPU inference
3. **TMDB**: API key for metadata

### On Your Machine
- Docker and Docker Compose
- Git
- SSH access to Hetzner VM

## Quick Start

### 1. Setup Hetzner VM

```bash
# SSH to your Hetzner VM
ssh root@your-hetzner-ip

# Clone repository
git clone <your-repo-url>
cd video-organizer

# Run setup script
chmod +x scripts/setup.sh
./scripts/setup.sh
```

The setup script will:
- Install Docker, rclone, dependencies
- Configure Hetzner Storage Box mount
- Setup database and services
- Create systemd service

### 2. Configure Environment

Edit `.env` file:

```bash
nano .env
```

Required variables:
```env
# Hetzner Storage Box
HETZNER_STORAGE_HOST=u123456.your-storagebox.de
HETZNER_STORAGE_USER=u123456
HETZNER_STORAGE_PASSWORD=your_password

# RunPod
RUNPOD_API_KEY=your_runpod_api_key
RUNPOD_ENDPOINT_ID=your_serverless_endpoint_id

# TMDB
TMDB_API_KEY=your_tmdb_api_key
```

### 3. Configure Cloud Sources

```bash
# Run rclone configuration
./scripts/install-rclone.sh
```

Follow prompts to authenticate:
- Google Drive
- OneDrive
- Any other remotes

### 4. Setup RunPod Endpoint

#### Option A: Serverless (Recommended for sporadic use)

```bash
# Build and push Docker image
cd runpod
docker build -t your-username/video-analyzer:latest .
docker push your-username/video-analyzer:latest

# Create endpoint in RunPod dashboard
# Use image: your-username/video-analyzer:latest
# Copy endpoint ID to .env
```

#### Option B: Spot Pod (For continuous processing)

```bash
# Deploy on RunPod:
# 1. Create spot pod with GPU (RTX 3090/4090)
# 2. Use image: your-username/video-analyzer:latest
# 3. Expose port 8000
# 4. Copy pod ID to .env
```

### 5. Start Services

```bash
# Start all services
docker-compose up -d

# Check logs
docker-compose logs -f

# Check status
docker-compose ps
```

## Usage

### Web Dashboard

Access at: `http://your-hetzner-ip:8080`

Features:
- View processing status
- Monitor queues
- Manual video reprocessing
- Statistics and costs

### Manual Sync

```bash
# Trigger immediate sync
docker-compose exec ingestion python sync_sources.py --once
```

### View Progress

```bash
# Watch all logs
docker-compose logs -f

# Watch specific service
docker-compose logs -f analyzer

# Database stats
docker-compose exec postgres psql -U videoorg -d video_organizer -c "
SELECT 
    status, 
    COUNT(*) as count,
    SUM(file_size)/1024/1024/1024 as total_gb
FROM videos 
GROUP BY status;"
```

## Configuration

### Sync Sources

Add/modify in database:

```sql
INSERT INTO sync_sources (source_name, source_type, source_path, enabled)
VALUES ('My Drive', 'gdrive', 'gdrive:Videos', true);
```

### Processing Settings

In `.env`:
```env
FRAME_EXTRACT_INTERVAL=30    # Extract frame every N seconds
MAX_CONCURRENT_ANALYSIS=3    # Parallel analysis jobs
BATCH_SIZE=5                 # Videos per batch
SYNC_INTERVAL=3600          # Sync every N seconds
```

### Jellyfin Paths

Customize in `.env`:
```env
JELLYFIN_MOVIES_PATH=/organized/Movies
JELLYFIN_TV_PATH=/organized/TV Shows
JELLYFIN_OTHER_PATH=/organized/Other
```

## Project Structure

```
video-organizer/
├── services/
│   ├── ingestion/          # Sync from cloud sources
│   ├── analyzer/           # Video analysis (coordinates RunPod)
│   ├── organizer/          # TMDB matching and Jellyfin naming
│   ├── api/                # Web dashboard
│   └── worker/             # Job processor
├── runpod/                 # GPU inference handler
├── scripts/                # Setup and utility scripts
├── config/                 # Configuration files
└── sql/                    # Database schemas
```

## Data Flow

1. **Ingestion**: 
   - Rclone syncs from cloud sources to `/data/raw`
   - Files hashed and added to database
   - Queued for analysis

2. **Analysis**:
   - Extracts frames and audio
   - Sends to RunPod for GPU analysis
   - Stores results in database
   - Queued for organization

3. **Organization**:
   - Matches to TMDB/TVDB
   - Generates Jellyfin-compatible name
   - Copies to `/data/organized`
   - Creates NFO files
   - Syncs to Hetzner Storage Box

4. **Jellyfin**:
   - Mount Hetzner Storage Box on Jellyfin server
   - Point libraries to organized folders
   - Automatic metadata from NFO files

## Jellyfin Integration

On your Jellyfin server:

```bash
# Mount Hetzner Storage Box
sudo mkdir -p /mnt/hetzner
sudo mount -t cifs //u123456.your-storagebox.de/organized \
    /mnt/hetzner \
    -o username=u123456,password=your_password

# Or use rclone mount
rclone mount hetzner:/organized /mnt/hetzner --daemon

# Add libraries in Jellyfin
# Movies: /mnt/hetzner/Movies
# TV Shows: /mnt/hetzner/TV Shows
```

## Cost Estimates

### Hetzner
- **VM (CX11)**: ~€4/month (2 vCPU, 2GB RAM)
- **Storage Box (1TB)**: ~€3/month
- **Total**: ~€7/month

### RunPod
- **Serverless (RTX 4090)**: ~$0.0004/sec = $1.44/hour
- **Spot Pod (RTX 4090)**: ~$0.30/hour (70% cheaper)

### Example Processing Costs
- 100 videos @ 30min each = 50 hours content
- ~5 min analysis per video = 8.3 hours compute
- **Serverless**: ~$12
- **Spot**: ~$2.50

## Troubleshooting

### Rclone Authentication Issues

```bash
# Re-authenticate
rclone config reconnect gdrive:
rclone config reconnect onedrive:
```

### RunPod Connection Errors

```bash
# Test connection
curl https://api.runpod.ai/v2/<endpoint-id>/health \
  -H "Authorization: Bearer $RUNPOD_API_KEY"

# Check logs
docker-compose logs analyzer
```

### Database Issues

```bash
# Reset database
docker-compose down
docker volume rm video-organizer_postgres_data
docker-compose up -d postgres
docker-compose exec postgres psql -U videoorg -d video_organizer -f /docker-entrypoint-initdb.d/init.sql
```

### Storage Box Mount Issues

```bash
# Check mount
mount | grep hetzner

# Remount
sudo umount /mnt/hetzner-storage
sudo mount -a

# Check permissions
ls -la /mnt/hetzner-storage
```

## Maintenance

### Backup Database

```bash
docker-compose exec postgres pg_dump -U videoorg video_organizer > backup.sql
```

### Clear Processed Videos

```bash
# Remove analyzed raw videos
docker-compose exec ingestion python cleanup.py --days 7
```

### Update Services

```bash
git pull
docker-compose build
docker-compose up -d
```

## Performance Tuning

### For Large Libraries (10,000+ videos)

1. **Increase workers**:
```yaml
# docker-compose.yml
worker:
  deploy:
    replicas: 4  # Increase parallelism
```

2. **Batch processing**:
```env
BATCH_SIZE=10
MAX_CONCURRENT_ANALYSIS=5
```

3. **Use RunPod Spot Pods** for better cost/performance

4. **Enable Redis clustering** for high throughput

## Security

### Secure Your API Keys

```bash
# Use Docker secrets instead of .env
docker secret create runpod_key runpod_api_key.txt
```

### Firewall Rules

```bash
# Allow only necessary ports
ufw allow 22/tcp    # SSH
ufw allow 8080/tcp  # Dashboard
ufw enable
```

### Hetzner Storage Box

```bash
# Use SSH keys instead of passwords
ssh-copy-id u123456@u123456.your-storagebox.de
```

## FAQ

**Q: Can I use AWS S3 instead of Hetzner?**  
A: Yes, modify rclone config to use S3. Update HETZNER_* vars to S3_* equivalents.

**Q: What GPU do I need on RunPod?**  
A: RTX 3090 (24GB) minimum. RTX 4090 (24GB) recommended for speed.

**Q: How long does analysis take?**  
A: ~30-60 seconds per video on RTX 4090, depending on length.

**Q: Can I run without GPU?**  
A: Yes, but very slow. Set up CPU-only models or use OpenAI API fallback.

**Q: How accurate is the matching?**  
A: 85-95% for movies, 70-80% for TV shows. Manual review recommended.

## Contributing

Contributions welcome! Please submit PRs or open issues.

## License

MIT License - See LICENSE file

## Support

- Issues: GitHub Issues
- Discussions: GitHub Discussions
- Email: support@example.com

## Acknowledgments

- RunPod for GPU infrastructure
- Hetzner for affordable hosting
- TMDB for metadata API
- Hugging Face for models
