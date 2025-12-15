#!/usr/bin/env python3
"""
TMDB Matcher - Matches analyzed videos to TMDB/TVDB entries
"""

import os
import re
from typing import Dict, Optional, List
from datetime import datetime
from tmdbv3api import TMDb, Movie, TV, Search
from fuzzywuzzy import fuzz

class TMDBMatcher:
    def __init__(self):
        self.tmdb = TMDb()
        self.tmdb.api_key = os.getenv('TMDB_API_KEY')
        self.tmdb.language = 'en'
        
        self.movie = Movie()
        self.tv = TV()
        self.search = Search()
    
    def log(self, message, level='INFO'):
        timestamp = datetime.now().isoformat()
        print(f"[{timestamp}] [TMDBMatcher] [{level}] {message}", flush=True)
    
    def match_movie(
        self, 
        title: str, 
        year: Optional[int] = None,
        confidence_threshold: int = 70
    ) -> Optional[Dict]:
        """
        Match a movie to TMDB
        
        Args:
            title: Movie title
            year: Release year (optional)
            confidence_threshold: Minimum confidence score (0-100)
        
        Returns:
            Match dict or None
        """
        try:
            self.log(f"Searching for movie: {title} ({year})")
            
            # Search TMDB
            results = self.search.movies(title)
            
            if not results:
                self.log(f"No results found for: {title}", 'WARNING')
                return None
            
            # Find best match
            best_match = None
            best_score = 0
            
            for result in results[:10]:  # Check top 10
                # Calculate confidence score
                title_score = fuzz.ratio(
                    title.lower(),
                    result.title.lower()
                )
                
                # Year bonus if provided
                year_match = True
                if year and hasattr(result, 'release_date'):
                    try:
                        result_year = int(result.release_date.split('-')[0])
                        year_match = abs(result_year - year) <= 1  # Allow 1 year difference
                        if year_match:
                            title_score += 10  # Bonus for year match
                    except:
                        pass
                
                if title_score > best_score:
                    best_score = title_score
                    best_match = result
            
            if not best_match or best_score < confidence_threshold:
                self.log(f"No confident match found (score: {best_score})", 'WARNING')
                return None
            
            # Get full details
            details = self.movie.details(best_match.id)
            
            match = {
                'media_type': 'movie',
                'tmdb_id': details.id,
                'title': details.title,
                'original_title': details.original_title,
                'year': int(details.release_date.split('-')[0]) if details.release_date else None,
                'release_date': details.release_date,
                'overview': details.overview,
                'genres': [g['name'] for g in details.genres] if hasattr(details, 'genres') else [],
                'runtime': details.runtime,
                'imdb_id': details.imdb_id if hasattr(details, 'imdb_id') else None,
                'confidence': best_score / 100.0,
                'poster_path': details.poster_path,
                'backdrop_path': details.backdrop_path
            }
            
            self.log(f"Matched: {match['title']} ({match['year']}) - Confidence: {match['confidence']:.2f}")
            return match
            
        except Exception as e:
            self.log(f"Error matching movie: {e}", 'ERROR')
            return None
    
    def match_tv_show(
        self,
        title: str,
        season: Optional[int] = None,
        episode: Optional[int] = None,
        year: Optional[int] = None,
        confidence_threshold: int = 70
    ) -> Optional[Dict]:
        """
        Match a TV show episode to TMDB
        
        Args:
            title: Show title
            season: Season number
            episode: Episode number
            year: Year (optional)
            confidence_threshold: Minimum confidence score
        
        Returns:
            Match dict or None
        """
        try:
            self.log(f"Searching for TV show: {title} S{season}E{episode}")
            
            # Search for TV show
            results = self.search.tv_shows(title)
            
            if not results:
                self.log(f"No results found for: {title}", 'WARNING')
                return None
            
            # Find best match
            best_match = None
            best_score = 0
            
            for result in results[:10]:
                title_score = fuzz.ratio(
                    title.lower(),
                    result.name.lower()
                )
                
                # Year bonus
                if year and hasattr(result, 'first_air_date'):
                    try:
                        result_year = int(result.first_air_date.split('-')[0])
                        if abs(result_year - year) <= 2:
                            title_score += 10
                    except:
                        pass
                
                if title_score > best_score:
                    best_score = title_score
                    best_match = result
            
            if not best_match or best_score < confidence_threshold:
                self.log(f"No confident match found (score: {best_score})", 'WARNING')
                return None
            
            # Get show details
            show_details = self.tv.details(best_match.id)
            
            match = {
                'media_type': 'tv',
                'tmdb_id': show_details.id,
                'title': show_details.name,
                'original_title': show_details.original_name,
                'year': int(show_details.first_air_date.split('-')[0]) if show_details.first_air_date else None,
                'overview': show_details.overview,
                'genres': [g['name'] for g in show_details.genres] if hasattr(show_details, 'genres') else [],
                'confidence': best_score / 100.0,
                'poster_path': show_details.poster_path,
                'backdrop_path': show_details.backdrop_path,
                'season': season,
                'episode': episode,
                'episode_title': None
            }
            
            # Get episode details if season/episode provided
            if season and episode:
                try:
                    episode_details = self.tv.episode_details(
                        best_match.id,
                        season,
                        episode
                    )
                    match['episode_title'] = episode_details.name
                    match['episode_overview'] = episode_details.overview
                    match['episode_air_date'] = episode_details.air_date
                except Exception as e:
                    self.log(f"Could not fetch episode details: {e}", 'WARNING')
            
            self.log(f"Matched: {match['title']} S{season}E{episode} - Confidence: {match['confidence']:.2f}")
            return match
            
        except Exception as e:
            self.log(f"Error matching TV show: {e}", 'ERROR')
            return None
    
    def auto_match(self, analysis_result: Dict) -> Optional[Dict]:
        """
        Automatically match based on analysis results
        
        Args:
            analysis_result: Results from video analysis
        
        Returns:
            Match dict or None
        """
        content_type = analysis_result.get('content_type', 'unknown')
        title = analysis_result.get('detected_title') or analysis_result.get('title', '')
        year = analysis_result.get('detected_year') or analysis_result.get('year')
        
        if not title:
            self.log("No title found in analysis", 'WARNING')
            return None
        
        if content_type == 'movie':
            return self.match_movie(title, year)
            
        elif content_type == 'tv_episode':
            season = analysis_result.get('detected_season') or analysis_result.get('season')
            episode = analysis_result.get('detected_episode') or analysis_result.get('episode')
            
            return self.match_tv_show(title, season, episode, year)
        
        else:
            # Try both
            self.log(f"Unknown content type '{content_type}', trying both movie and TV")
            
            movie_match = self.match_movie(title, year, confidence_threshold=80)
            if movie_match and movie_match['confidence'] > 0.85:
                return movie_match
            
            tv_match = self.match_tv_show(title, year=year, confidence_threshold=80)
            if tv_match and tv_match['confidence'] > 0.85:
                return tv_match
            
            # Return best match
            if movie_match and tv_match:
                return movie_match if movie_match['confidence'] > tv_match['confidence'] else tv_match
            
            return movie_match or tv_match
