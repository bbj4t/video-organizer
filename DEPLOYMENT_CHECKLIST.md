# Deployment Checklist

Use this checklist to ensure everything is configured correctly.

## Pre-Deployment

### Accounts Setup
- [ ] Hetzner account created
- [ ] Hetzner Storage Box ordered (1TB minimum)
- [ ] Hetzner VM deployed (CX11 or better, Ubuntu 22.04)
- [ ] RunPod account created
- [ ] RunPod API key obtained
- [ ] TMDB account created
- [ ] TMDB API key obtained
- [ ] Docker Hub account (for RunPod image)

### Local Preparation
- [ ] SSH key generated (`ssh-keygen`)
- [ ] SSH access to Hetzner VM verified
- [ ] Git installed locally
- [ ] Code repository cloned

## Hetzner VM Setup

### Initial Configuration
- [ ] VM accessible via SSH
- [ ] System updated (`apt update && apt upgrade`)
- [ ] Firewall configured (ports 22, 8080)
- [ ] Non-root user created (if using root)

### Project Deployment
- [ ] Repository cloned to VM
- [ ] `deploy.sh` script executed
- [ ] All prompts answered
- [ ] No errors during installation
- [ ] Services started successfully

### Storage Box
- [ ] SSH key uploaded to Storage Box
- [ ] Storage Box mounted at `/mnt/hetzner-storage`
- [ ] Mount persists after reboot
- [ ] Write permissions verified

## Cloud Storage Configuration

### Rclone Setup
- [ ] Rclone installed
- [ ] Google Drive configured
- [ ] OneDrive configured
- [ ] Other sources configured (if any)
- [ ] Config copied to `~/video-organizer/config/rclone.conf`
- [ ] Test access: `rclone lsd gdrive:`
- [ ] Test access: `rclone lsd onedrive:`

### Sync Sources
- [ ] Sync sources added to database
- [ ] Paths verified correct
- [ ] Enabled status set to true

## RunPod Configuration

### Image Deployment
- [ ] Docker image built
- [ ] Image pushed to Docker Hub
- [ ] Image name noted

### Endpoint Setup (Choose One)

**Serverless:**
- [ ] Endpoint created in RunPod
- [ ] GPU type: RTX 4090 or better
- [ ] Docker image configured
- [ ] Endpoint ID copied
- [ ] Endpoint ID added to `.env`
- [ ] Test endpoint: `curl` health check

**Spot Pod:**
- [ ] Spot pod deployed
- [ ] GPU type: RTX 4090 or better
- [ ] Docker image configured
- [ ] Port 8000 exposed
- [ ] Pod ID copied
- [ ] Pod ID added to `.env`

## Service Verification

### Docker Services
- [ ] All containers running: `docker-compose ps`
- [ ] PostgreSQL accessible
- [ ] Redis accessible
- [ ] No crash loops in logs

### Database
- [ ] Database initialized
- [ ] Tables created
- [ ] Test query successful

### Ingestion Service
- [ ] Container running
- [ ] Logs show sync attempts
- [ ] No authentication errors
- [ ] Files appearing in `/data/raw`

### Analyzer Service
- [ ] Container running
- [ ] RunPod connection successful
- [ ] Test analysis completed
- [ ] No GPU errors

### Organizer Service
- [ ] Container running
- [ ] TMDB API working
- [ ] Files organized to correct paths
- [ ] NFO files created

### API Service
- [ ] Container running
- [ ] Dashboard accessible at `http://IP:8080`
- [ ] No 404 or 500 errors

## Integration Testing

### End-to-End Test
- [ ] Test video added to source
- [ ] Video detected by ingestion
- [ ] Video analyzed by RunPod
- [ ] Video matched to TMDB
- [ ] Video organized with correct name
- [ ] NFO file created
- [ ] File synced to Hetzner

### Jellyfin Connection
- [ ] Hetzner Storage mounted on Jellyfin server
- [ ] Libraries added in Jellyfin
- [ ] Metadata detected from NFO
- [ ] Videos playable

## Monitoring Setup

### Logs
- [ ] Log aggregation working
- [ ] Error logs reviewed
- [ ] No critical errors

### Alerts
- [ ] Email notifications configured (optional)
- [ ] Disk space monitoring active
- [ ] Queue size monitoring active

## Performance Optimization

### Queue Management
- [ ] Worker count adjusted for load
- [ ] Redis performing well
- [ ] No queue backlog

### Resource Usage
- [ ] CPU usage acceptable (<80% average)
- [ ] Memory usage acceptable (<80% of RAM)
- [ ] Disk usage monitored
- [ ] Network bandwidth sufficient

### Cost Optimization
- [ ] RunPod usage tracked
- [ ] Spot pods used for batch processing
- [ ] Idle resources stopped

## Security Hardening

### Credentials
- [ ] All passwords in `.env` file
- [ ] `.env` file permissions restricted (600)
- [ ] No credentials in git history
- [ ] API keys rotated if leaked

### Network Security
- [ ] Firewall enabled
- [ ] Only necessary ports open
- [ ] SSH key-only authentication
- [ ] Fail2ban installed (optional)

### Data Protection
- [ ] Database backups configured
- [ ] Backup location verified
- [ ] Restore procedure tested

## Documentation

### Local Documentation
- [ ] `.env` file documented
- [ ] Custom configurations noted
- [ ] Contact information updated
- [ ] Team members notified

## Go-Live Checklist

### Final Verification
- [ ] All above items checked
- [ ] Test video processed successfully
- [ ] Dashboard shows correct stats
- [ ] Jellyfin displays media correctly
- [ ] No errors in logs for 24 hours

### Handoff
- [ ] Admin credentials shared (securely)
- [ ] Documentation provided
- [ ] Support contact established
- [ ] Monitoring access granted

## Post-Deployment

### Week 1
- [ ] Monitor logs daily
- [ ] Check queue sizes
- [ ] Review costs
- [ ] Verify all syncs working

### Month 1
- [ ] Database backup verified
- [ ] Performance metrics reviewed
- [ ] Cost analysis completed
- [ ] Optimization opportunities identified

### Ongoing
- [ ] Monthly cost review
- [ ] Quarterly system updates
- [ ] Annual security audit
- [ ] Continuous improvement

## Rollback Plan

If something goes wrong:

1. **Stop Services:**
   ```bash
   docker-compose down
   ```

2. **Restore Database:**
   ```bash
   docker-compose exec postgres psql ... < backup.sql
   ```

3. **Check Logs:**
   ```bash
   docker-compose logs > issue-logs.txt
   ```

4. **Contact Support:**
   - Include logs
   - Describe issue
   - List what was working before

## Notes Section

Use this space for deployment-specific notes:

```
Date Deployed: _______________
Deployed By: __________________
Hetzner VM IP: _______________
Storage Box ID: ______________
RunPod Endpoint: _____________
Issues Encountered:


Resolutions:


Custom Modifications:


```

---

**Deployment Completed:** [ ] YES / [ ] NO

**Sign-off:** _________________ **Date:** _________
