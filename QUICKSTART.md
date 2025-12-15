# Quick Start Guide

Get your video organizer running in under 30 minutes.

## Prerequisites Checklist

Before you begin, have these ready:

- [ ] Hetzner account with Storage Box (1TB minimum)
- [ ] RunPod account with API key
- [ ] TMDB account with API key
- [ ] SSH access to a Hetzner VM (CX11 or better)

## One-Command Setup

SSH to your Hetzner VM and run:

```bash
git clone https://github.com/yourusername/video-organizer.git
cd video-organizer
chmod +x deploy.sh
./deploy.sh
```

The script will prompt you for:
1. Hetzner Storage Box credentials
2. RunPod API key
3. TMDB API key

That's it! ☕ Grab a coffee while it installs.

## What Gets Installed

- Docker & Docker Compose
- Rclone for cloud sync
- PostgreSQL database
- Redis queue
- All microservices
- Hetzner Storage Box mount
- Systemd service

## Configure Cloud Sources

After installation, configure your cloud storage:

```bash
# Run this to add Google Drive, OneDrive, etc.
./scripts/install-rclone.sh
```

Follow the interactive prompts to authenticate each service.

## Deploy RunPod Analyzer

```bash
# Deploy GPU inference handler
./scripts/deploy-runpod.sh
```

This will:
1. Build Docker image
2. Push to Docker Hub
3. Give you instructions for RunPod setup

In RunPod dashboard:
- Create Serverless Endpoint
- Use your pushed image
- Copy Endpoint ID to `.env`

## Add Your Videos

### Option 1: Local Files
```bash
cp -r /path/to/your/videos/* ~/video-organizer/local_media/
```

### Option 2: Already in Cloud
They'll be synced automatically from Google Drive/OneDrive!

## Start Processing

Services auto-start, but you can manually trigger:

```bash
cd ~/video-organizer

# View what's happening
docker-compose logs -f

# Check status
docker-compose ps

# View database
docker-compose exec postgres psql -U videoorg -d video_organizer -c "
SELECT status, COUNT(*) FROM videos GROUP BY status;"
```

## Access Dashboard

Open in browser:
```
http://YOUR_HETZNER_IP:8080
```

## Connect Jellyfin

On your Jellyfin server:

```bash
# Mount storage
sudo mkdir -p /mnt/videos
rclone mount hetzner:/organized /mnt/videos --daemon \
  --vfs-cache-mode writes

# Add libraries in Jellyfin UI
Movies: /mnt/videos/Movies
TV Shows: /mnt/videos/TV Shows
```

## Verify Everything Works

```bash
# Check all services running
docker-compose ps
# All should show "Up"

# Check storage mount
ls -la /mnt/hetzner-storage
# Should show files

# Check rclone
rclone listremotes
# Should show: gdrive:, onedrive:, hetzner:

# Test RunPod connection
curl -X POST https://api.runpod.ai/v2/YOUR_ENDPOINT_ID/health \
  -H "Authorization: Bearer YOUR_API_KEY"
# Should return: {"status":"ok"}

# Check database
docker-compose exec postgres psql -U videoorg -d video_organizer -c "\dt"
# Should show all tables
```

## Common Issues

### Can't connect to Hetzner Storage
```bash
# Check mount
mount | grep hetzner

# Remount if needed
sudo umount /mnt/hetzner-storage
sudo mount -a
```

### Rclone auth expired
```bash
rclone config reconnect gdrive:
rclone config reconnect onedrive:
```

### Services won't start
```bash
# Check logs
docker-compose logs

# Restart specific service
docker-compose restart analyzer
```

### Database errors
```bash
# Reset database (WARNING: deletes all data)
docker-compose down
docker volume rm video-organizer_postgres_data
docker-compose up -d
```

## Daily Operation

The system runs automatically, but useful commands:

```bash
# View logs
docker-compose logs -f ingestion  # Sync progress
docker-compose logs -f analyzer   # Analysis progress
docker-compose logs -f organizer  # Organization progress

# Manual sync trigger
docker-compose restart ingestion

# Check queue sizes
docker-compose exec redis redis-cli llen analysis_queue
docker-compose exec redis redis-cli llen organization_queue

# Stats
docker-compose exec postgres psql -U videoorg -d video_organizer -c "
SELECT 
  COUNT(*) as total,
  COUNT(*) FILTER (WHERE status='organized') as organized,
  COUNT(*) FILTER (WHERE status='pending') as pending,
  COUNT(*) FILTER (WHERE status='analyzing') as analyzing,
  COUNT(*) FILTER (WHERE status='error') as errors
FROM videos;"
```

## Cost Summary

Monthly costs (estimated):

**Hetzner:**
- VM (CX11): €4/mo
- Storage Box 1TB: €3/mo
- **Total: €7/mo (~$7.50)**

**RunPod (variable based on usage):**
- 100 videos/month: ~$1-2
- 1000 videos/month: ~$10-20

**TMDB:**
- Free (no cost)

## Next Steps

1. ✅ System running
2. ✅ Videos syncing
3. ✅ Analysis working
4. ✅ Organization happening
5. ⏭️ Configure Jellyfin
6. ⏭️ Customize naming rules
7. ⏭️ Setup monitoring/alerts
8. ⏭️ Add more cloud sources

## Get Help

- Check logs: `docker-compose logs -f`
- View full README: `cat README.md`
- GitHub Issues: [Link to your repo]

## Pro Tips

1. **Start Small**: Test with 10-20 videos first
2. **Monitor Costs**: Check RunPod dashboard daily
3. **Use Serverless**: Unless processing 1000+ videos/month
4. **Backup Database**: `docker-compose exec postgres pg_dump...`
5. **Watch the Logs**: They tell you everything

---

**That's it!** Your automated video library organizer is now running. 

Videos will be:
- ✓ Synced from all sources
- ✓ Analyzed with AI
- ✓ Matched to TMDB
- ✓ Named for Jellyfin
- ✓ Organized automatically

Enjoy your perfectly organized media library! 🎬🍿
