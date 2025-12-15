#!/usr/bin/env python3
"""
Jellyfin Naming - Generates Jellyfin-compatible file paths and names
"""

import os
import re
from pathlib import Path
from typing import Dict, Optional

class JellyfinNamer:
    def __init__(self):
        self.movies_path = os.getenv('JELLYFIN_MOVIES_PATH', '/organized/Movies')
        self.tv_path = os.getenv('JELLYFIN_TV_PATH', '/organized/TV Shows')
        self.other_path = os.getenv('JELLYFIN_OTHER_PATH', '/organized/Other')
    
    @staticmethod
    def sanitize_filename(name: str) -> str:
        """Remove invalid characters from filename"""
        # Replace invalid characters
        invalid_chars = r'[<>:"/\\|?*]'
        name = re.sub(invalid_chars, '', name)
        
        # Replace multiple spaces with single space
        name = re.sub(r'\s+', ' ', name)
        
        # Trim
        name = name.strip()
        
        return name
    
    def generate_movie_path(
        self, 
        match: Dict, 
        original_extension: str = '.mkv'
    ) -> str:
        """
        Generate Jellyfin-compatible path for a movie
        
        Format: /Movies/Movie Name (Year)/Movie Name (Year).ext
        
        Args:
            match: TMDB match dict
            original_extension: Original file extension
        
        Returns:
            Full path for organized file
        """
        title = self.sanitize_filename(match['title'])
        year = match.get('year', 'Unknown')
        
        # Movie folder name
        folder_name = f"{title} ({year})"
        
        # Movie filename
        filename = f"{title} ({year}){original_extension}"
        
        # Full path
        full_path = os.path.join(
            self.movies_path,
            folder_name,
            filename
        )
        
        return full_path
    
    def generate_tv_path(
        self,
        match: Dict,
        original_extension: str = '.mkv'
    ) -> str:
        """
        Generate Jellyfin-compatible path for a TV episode
        
        Format: /TV Shows/Show Name/Season XX/Show Name - sXXeXX - Episode Name.ext
        
        Args:
            match: TMDB match dict
            original_extension: Original file extension
        
        Returns:
            Full path for organized file
        """
        show_title = self.sanitize_filename(match['title'])
        season = match.get('season', 1)
        episode = match.get('episode', 1)
        episode_title = match.get('episode_title', '')
        
        # Season folder
        season_folder = f"Season {season:02d}"
        
        # Episode filename
        episode_name = f"{show_title} - s{season:02d}e{episode:02d}"
        
        if episode_title:
            episode_title_clean = self.sanitize_filename(episode_title)
            episode_name += f" - {episode_title_clean}"
        
        episode_name += original_extension
        
        # Full path
        full_path = os.path.join(
            self.tv_path,
            show_title,
            season_folder,
            episode_name
        )
        
        return full_path
    
    def generate_path(
        self,
        match: Dict,
        original_extension: str = '.mkv'
    ) -> str:
        """
        Generate appropriate path based on media type
        
        Args:
            match: TMDB match dict
            original_extension: Original file extension
        
        Returns:
            Full path for organized file
        """
        media_type = match.get('media_type', 'unknown')
        
        if media_type == 'movie':
            return self.generate_movie_path(match, original_extension)
        elif media_type == 'tv':
            return self.generate_tv_path(match, original_extension)
        else:
            # Unknown type - place in Other
            filename = self.sanitize_filename(
                match.get('title', 'Unknown') + original_extension
            )
            return os.path.join(self.other_path, filename)
    
    def create_nfo_file(self, match: Dict, video_path: str) -> Optional[str]:
        """
        Create .nfo file for Jellyfin metadata
        
        Args:
            match: TMDB match dict
            video_path: Path to video file
        
        Returns:
            Path to created .nfo file
        """
        nfo_path = Path(video_path).with_suffix('.nfo')
        
        try:
            media_type = match.get('media_type')
            
            if media_type == 'movie':
                nfo_content = self._generate_movie_nfo(match)
            elif media_type == 'tv':
                nfo_content = self._generate_episode_nfo(match)
            else:
                return None
            
            with open(nfo_path, 'w', encoding='utf-8') as f:
                f.write(nfo_content)
            
            return str(nfo_path)
            
        except Exception as e:
            print(f"Error creating NFO: {e}")
            return None
    
    def _generate_movie_nfo(self, match: Dict) -> str:
        """Generate NFO content for movie"""
        tmdb_id = match.get('tmdb_id', '')
        imdb_id = match.get('imdb_id', '')
        
        nfo = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<movie>
    <title>{match.get('title', '')}</title>
    <originaltitle>{match.get('original_title', '')}</originaltitle>
    <year>{match.get('year', '')}</year>
    <plot>{match.get('overview', '')}</plot>
    <runtime>{match.get('runtime', '')}</runtime>
    <tmdbid>{tmdb_id}</tmdbid>
"""
        
        if imdb_id:
            nfo += f"    <imdbid>{imdb_id}</imdbid>\n"
        
        # Add genres
        for genre in match.get('genres', []):
            nfo += f"    <genre>{genre}</genre>\n"
        
        nfo += "</movie>"
        
        return nfo
    
    def _generate_episode_nfo(self, match: Dict) -> str:
        """Generate NFO content for TV episode"""
        tmdb_id = match.get('tmdb_id', '')
        season = match.get('season', 1)
        episode = match.get('episode', 1)
        
        nfo = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<episodedetails>
    <title>{match.get('episode_title', '')}</title>
    <showtitle>{match.get('title', '')}</showtitle>
    <season>{season}</season>
    <episode>{episode}</episode>
    <plot>{match.get('episode_overview', '')}</plot>
    <tmdbid>{tmdb_id}</tmdbid>
    <aired>{match.get('episode_air_date', '')}</aired>
</episodedetails>
"""
        
        return nfo
