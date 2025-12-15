-- Video Organizer Database Schema

-- Videos table
CREATE TABLE IF NOT EXISTS videos (
    id SERIAL PRIMARY KEY,
    source_path TEXT NOT NULL,
    source_type VARCHAR(50), -- 'gdrive', 'onedrive', 'local', etc.
    file_hash VARCHAR(64) UNIQUE,
    file_size BIGINT,
    duration FLOAT,
    resolution VARCHAR(20),
    codec VARCHAR(50),
    status VARCHAR(50) DEFAULT 'pending', -- pending, analyzing, analyzed, organizing, organized, error
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Analysis results
CREATE TABLE IF NOT EXISTS analysis_results (
    id SERIAL PRIMARY KEY,
    video_id INTEGER REFERENCES videos(id) ON DELETE CASCADE,
    content_type VARCHAR(50), -- 'movie', 'tv_episode', 'documentary', 'other'
    detected_title TEXT,
    detected_year INTEGER,
    detected_season INTEGER,
    detected_episode INTEGER,
    confidence_score FLOAT,
    ai_description TEXT,
    audio_language VARCHAR(10),
    subtitle_languages TEXT[], -- array of language codes
    scene_tags TEXT[],
    analysis_metadata JSONB, -- full analysis data
    created_at TIMESTAMP DEFAULT NOW()
);

-- TMDB/TVDB matches
CREATE TABLE IF NOT EXISTS media_matches (
    id SERIAL PRIMARY KEY,
    video_id INTEGER REFERENCES videos(id) ON DELETE CASCADE,
    media_type VARCHAR(20), -- 'movie' or 'tv'
    tmdb_id INTEGER,
    tvdb_id INTEGER,
    title TEXT,
    year INTEGER,
    season INTEGER,
    episode INTEGER,
    episode_title TEXT,
    match_confidence FLOAT,
    metadata JSONB, -- full TMDB/TVDB data
    created_at TIMESTAMP DEFAULT NOW()
);

-- Organized files
CREATE TABLE IF NOT EXISTS organized_files (
    id SERIAL PRIMARY KEY,
    video_id INTEGER REFERENCES videos(id) ON DELETE CASCADE,
    jellyfin_path TEXT NOT NULL,
    hetzner_path TEXT NOT NULL,
    file_size BIGINT,
    organized_at TIMESTAMP DEFAULT NOW()
);

-- Processing jobs
CREATE TABLE IF NOT EXISTS jobs (
    id SERIAL PRIMARY KEY,
    job_type VARCHAR(50), -- 'sync', 'analyze', 'organize'
    video_id INTEGER REFERENCES videos(id) ON DELETE CASCADE,
    status VARCHAR(50) DEFAULT 'queued', -- queued, processing, completed, failed
    priority INTEGER DEFAULT 5,
    attempts INTEGER DEFAULT 0,
    max_attempts INTEGER DEFAULT 3,
    error_message TEXT,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Sync sources tracking
CREATE TABLE IF NOT EXISTS sync_sources (
    id SERIAL PRIMARY KEY,
    source_name VARCHAR(100) NOT NULL,
    source_type VARCHAR(50), -- 'gdrive', 'onedrive', 'local'
    source_path TEXT NOT NULL,
    last_sync TIMESTAMP,
    files_synced INTEGER DEFAULT 0,
    bytes_synced BIGINT DEFAULT 0,
    enabled BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- System stats
CREATE TABLE IF NOT EXISTS stats (
    id SERIAL PRIMARY KEY,
    stat_date DATE DEFAULT CURRENT_DATE,
    total_videos INTEGER DEFAULT 0,
    videos_analyzed INTEGER DEFAULT 0,
    videos_organized INTEGER DEFAULT 0,
    total_storage_bytes BIGINT DEFAULT 0,
    processing_time_seconds INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_videos_status ON videos(status);
CREATE INDEX IF NOT EXISTS idx_videos_hash ON videos(file_hash);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status, priority DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_video_id ON jobs(video_id);
CREATE INDEX IF NOT EXISTS idx_analysis_video_id ON analysis_results(video_id);
CREATE INDEX IF NOT EXISTS idx_matches_video_id ON media_matches(video_id);
CREATE INDEX IF NOT EXISTS idx_organized_video_id ON organized_files(video_id);

-- Updated at trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply trigger to tables
CREATE TRIGGER update_videos_updated_at BEFORE UPDATE ON videos
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_jobs_updated_at BEFORE UPDATE ON jobs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_sync_sources_updated_at BEFORE UPDATE ON sync_sources
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
