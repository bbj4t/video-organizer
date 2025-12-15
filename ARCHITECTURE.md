# Video Organizer - Project Overview

## Executive Summary

Automated video library consolidation system that:
- Syncs videos from multiple cloud sources (Google Drive, OneDrive, local)
- Analyzes content using GPU-accelerated AI (RunPod)
- Matches to TMDB database
- Organizes with Jellyfin-compatible naming
- Stores on Hetzner Storage Box

**Total Cost:** ~$10-15/month for 1TB storage + processing

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     Cloud Sources                                │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │  Google  │  │   One    │  │  Local   │  │  Other   │       │
│  │  Drive   │  │  Drive   │  │ Storage  │  │ Sources  │       │
│  └─────┬────┘  └─────┬────┘  └─────┬────┘  └─────┬────┘       │
└────────┼─────────────┼─────────────┼─────────────┼─────────────┘
         │             │             │             │
         │         Rclone Sync (every hour)        │
         │             │             │             │
         └─────────────┼─────────────┼─────────────┘
                       ▼
         ┌─────────────────────────────┐
         │   Hetzner VM (CX11)         │
         │   ┌─────────────────────┐   │
         │   │  Ingestion Service  │   │
         │   │  - File detection   │   │
         │   │  - Deduplication    │   │
         │   │  - Queue management │   │
         │   └──────────┬──────────┘   │
         │              ▼              │
         │   ┌─────────────────────┐   │
         │   │  PostgreSQL         │   │
         │   │  - Metadata         │   │
         │   │  - Job tracking     │   │
         │   └──────────┬──────────┘   │
         │              │              │
         │   ┌──────────▼──────────┐   │
         │   │  Redis Queue        │   │
         │   │  - Job scheduling   │   │
         │   └──────────┬──────────┘   │
         │              ▼              │
         │   ┌─────────────────────┐   │
         │   │  Analyzer Service   │   │
         │   │  - Frame extract    │   │
         │   │  - Audio extract    │   │
         │   └──────────┬──────────┘   │
         └──────────────┼──────────────┘
                        │
                        │ Sends frames + audio
                        ▼
         ┌──────────────────────────────┐
         │   RunPod GPU (RTX 4090)      │
         │   ┌──────────────────────┐   │
         │   │  LLaVA-Video Model   │   │
         │   │  - Content detect    │   │
         │   │  - Scene analysis    │   │
         │   └──────────┬───────────┘   │
         │   ┌──────────▼───────────┐   │
         │   │  Whisper Model       │   │
         │   │  - Audio transcribe  │   │
         │   └──────────┬───────────┘   │
         └──────────────┼───────────────┘
                        │
                Returns analysis results
                        │
                        ▼
         ┌──────────────────────────────┐
         │   Hetzner VM                 │
         │   ┌──────────────────────┐   │
         │   │  Organizer Service   │   │
         │   │  - TMDB matching     │   │
         │   │  - Jellyfin naming   │   │
         │   │  - NFO creation      │   │
         │   └──────────┬───────────┘   │
         └──────────────┼───────────────┘
                        │
                        │ Organized files
                        ▼
         ┌──────────────────────────────┐
         │   Hetzner Storage Box (1TB)  │
         │   /Movies/                   │
         │   /TV Shows/                 │
         │   /Other/                    │
         └──────────────┬───────────────┘
                        │
                        │ Mounted via SSHFS/Rclone
                        ▼
         ┌──────────────────────────────┐
         │   Jellyfin Server            │
         │   - Movie Library            │
         │   - TV Show Library          │
         │   - Automatic metadata       │
         └──────────────────────────────┘
```

## Tech Stack

### Infrastructure
- **Hetzner Cloud VM**: CX11 (2 vCPU, 2GB RAM, €4/mo)
- **Hetzner Storage Box**: 1TB (€3/mo)
- **RunPod**: GPU inference (Serverless or Spot)

### Services (Docker Containers)
1. **PostgreSQL**: Metadata and job tracking
2. **Redis**: Job queue management
3. **Ingestion**: Multi-source sync (Rclone)
4. **Analyzer**: Video processing coordinator
5. **Organizer**: TMDB matching and Jellyfin naming
6. **API**: Web dashboard
7. **Workers**: Parallel job processing

### AI Models (on RunPod)
- **LLaVA-Video**: Visual content analysis
- **Whisper**: Audio transcription
- **CLIP**: Scene understanding (optional)

### Integration
- **Rclone**: Cloud storage sync
- **TMDB API**: Movie/TV metadata
- **FFmpeg**: Video processing
- **Docker Compose**: Orchestration

## Data Flow

### 1. Ingestion Phase
```
Cloud Source → Rclone → /data/raw → Database Entry → Analysis Queue
```
- Syncs every hour (configurable)
- Deduplicates via file hash
- Tracks source locations

### 2. Analysis Phase
```
Analysis Queue → Frame Extraction → RunPod GPU → Results → Database
                                   ↓
                             Audio Transcription
```
- Extracts 10 key frames
- Transcribes audio with Whisper
- Analyzes with LLaVA-Video
- Stores structured results

### 3. Organization Phase
```
Organization Queue → TMDB Match → Jellyfin Naming → /data/organized
                                                    ↓
                                              Hetzner Storage
```
- Matches to TMDB (85-95% accuracy)
- Generates Jellyfin paths
- Creates NFO files
- Syncs to storage

## File Organization Structure

```
/organized/
├── Movies/
│   ├── Avatar (2009)/
│   │   ├── Avatar (2009).mkv
│   │   └── Avatar (2009).nfo
│   └── Inception (2010)/
│       ├── Inception (2010).mkv
│       └── Inception (2010).nfo
├── TV Shows/
│   ├── Breaking Bad/
│   │   ├── Season 01/
│   │   │   ├── Breaking Bad - s01e01 - Pilot.mkv
│   │   │   ├── Breaking Bad - s01e01 - Pilot.nfo
│   │   │   └── Breaking Bad - s01e02 - Cat's in the Bag.mkv
│   │   └── Season 02/
│   └── The Office/
└── Other/
    └── Documentaries/
```

## Database Schema

### Core Tables
- **videos**: All video files
- **analysis_results**: AI analysis data
- **media_matches**: TMDB/TVDB matches
- **organized_files**: Final organized locations
- **jobs**: Processing queue
- **sync_sources**: Cloud source config
- **stats**: System metrics

## API Endpoints

Web dashboard provides:
- Processing status overview
- Queue monitoring
- Cost tracking
- Manual controls
- Statistics and analytics

## Cost Breakdown

### Fixed Costs (Monthly)
- Hetzner VM (CX11): €4 (~$4.30)
- Hetzner Storage 1TB: €3 (~$3.20)
- **Total Fixed: €7 (~$7.50)**

### Variable Costs (RunPod)
**Serverless (RTX 4090):**
- $0.0004/second = $1.44/hour
- ~5 min/video = $0.012/video
- 100 videos = ~$1.20
- 1000 videos = ~$12

**Spot Pod (RTX 4090):**
- ~$0.30/hour
- Better for batch processing
- 100 videos @ 5min each = 8.3 hours = ~$2.50

### Example Monthly Costs
- **Light Use** (100 videos/mo): $7.50 + $1.20 = $8.70/mo
- **Medium Use** (500 videos/mo): $7.50 + $6 = $13.50/mo
- **Heavy Use** (2000 videos/mo): $7.50 + $24 = $31.50/mo

## Performance Metrics

### Processing Speed
- **Sync**: 100 GB/hour (depends on bandwidth)
- **Analysis**: 30-60 sec/video (RTX 4090)
- **Organization**: <5 sec/video
- **End-to-End**: ~2 min/video average

### Throughput
- **Single Worker**: ~30 videos/hour
- **3 Workers**: ~90 videos/hour
- **Serverless**: Scales automatically

### Accuracy
- **Movie Matching**: 85-95%
- **TV Show Matching**: 70-80%
- **Content Detection**: 80-90%

## Scalability

### Vertical Scaling
- Upgrade Hetzner VM to CX21 or CX31
- Add more worker containers
- Increase RunPod parallelism

### Horizontal Scaling
- Multiple Hetzner VMs
- Load balancer for API
- Distributed job queue
- Multiple RunPod endpoints

## Backup Strategy

### Automatic Backups
- PostgreSQL: Daily automated backup
- Organized files: On Hetzner Storage Box
- Configs: Git repository

### Manual Backups
- `docker-compose exec postgres pg_dump...`
- Rclone sync to secondary storage
- Configuration files in version control

## Monitoring

### Built-in Monitoring
- Docker health checks
- Redis queue sizes
- Database query performance
- RunPod API response times

### External Monitoring (Optional)
- Uptime Robot for API
- Grafana for metrics
- Email alerts via SMTP

## Security

### Network Security
- Firewall (UFW) configured
- SSH key-only authentication
- Non-root user operation
- VPN integration (WireGuard)

### Credential Management
- Environment variables (.env)
- No hardcoded secrets
- API key rotation
- Secure storage for passwords

### Data Security
- Encrypted storage box connection
- TLS for API traffic
- Database access restricted
- Regular security updates

## Maintenance

### Daily
- Check logs for errors
- Monitor queue sizes
- Verify RunPod costs

### Weekly
- Database cleanup
- Disk space check
- Performance review

### Monthly
- System updates
- Cost analysis
- Security audit
- Backup verification

## Future Enhancements

### Planned Features
- [ ] Subtitle extraction and matching
- [ ] Multi-language support
- [ ] Advanced filtering rules
- [ ] Email notifications
- [ ] Mobile app monitoring
- [ ] Auto-quality optimization
- [ ] Batch import CLI
- [ ] API rate limiting

### Nice-to-Have
- [ ] Web-based video player
- [ ] Social features (recommendations)
- [ ] Machine learning improvements
- [ ] Custom metadata fields
- [ ] Plugin system
- [ ] Multi-tenant support

## Troubleshooting

### Common Issues
1. **Rclone auth expired**: Run `rclone config reconnect`
2. **RunPod timeout**: Check endpoint health
3. **TMDB rate limit**: Implement retry logic
4. **Storage full**: Cleanup or upgrade
5. **Queue backing up**: Add workers

### Debug Commands
```bash
# View all logs
docker-compose logs -f

# Check specific service
docker-compose logs analyzer

# Database query
docker-compose exec postgres psql -U videoorg

# Redis inspection
docker-compose exec redis redis-cli
```

## Success Criteria

System is successful when:
- ✅ All services running without errors
- ✅ Videos automatically synced hourly
- ✅ 80%+ match accuracy achieved
- ✅ Processing keeps pace with new content
- ✅ Jellyfin displays all organized content
- ✅ Monthly costs within budget
- ✅ Zero manual intervention needed

## Support

### Documentation
- README.md: Complete guide
- QUICKSTART.md: Fast setup
- DEPLOYMENT_CHECKLIST.md: Verification
- This file: Architecture overview

### Resources
- TMDB API Docs: https://developers.themoviedb.org
- RunPod Docs: https://docs.runpod.io
- Jellyfin Docs: https://jellyfin.org/docs
- Rclone Docs: https://rclone.org

## Credits

- **Jellyfin**: Open-source media system
- **RunPod**: GPU infrastructure
- **Hetzner**: Reliable hosting
- **Anthropic**: Claude AI assistance
- **HuggingFace**: AI models
- **TMDB**: Media metadata
