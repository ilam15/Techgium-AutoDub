"""
YouTube Video Downloader Module
Handles fetching video information and downloading videos with quality selection
"""

import yt_dlp
import os
import logging
from typing import Dict, List, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("YouTubeDownloader")


class YouTubeDownloader:
    """
    High-performance YouTube downloader with quality selection support
    """
    
    def __init__(self, download_dir: str = "temp_downloads"):
        """
        Initialize YouTube downloader
        
        Args:
            download_dir: Directory to save downloaded videos
        """
        self.download_dir = download_dir
        os.makedirs(download_dir, exist_ok=True)
        
        # Point 8: yt-dlp Stability Check
        try:
            from yt_dlp import version
            current_version = version.__version__
            logger.info(f"yt-dlp version: {current_version}")
            # Simple check: warn if version is older than 2024.
            if int(current_version.split('.')[0]) < 2024:
                 logger.warning(f"yt-dlp version {current_version} is old! Please upgrade to avoid PO Token errors.")
        except Exception:
             logger.warning("Could not verify yt-dlp version.")
    
    def get_video_info(self, url: str) -> Dict:
        """
        Fetch video information including available formats
        
        Args:
            url: YouTube video URL
            
        Returns:
            Dictionary containing video metadata and available formats
        """
        try:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,
                # Fix 403 Forbidden errors
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'en-us,en;q=0.5',
                    'Sec-Fetch-Mode': 'navigate',
                },
                # Use Node.js for JavaScript execution (fixes JS runtime warning)
                'extractor_args': {
                    'youtube': {
                        'player_client': ['android', 'web'],
                        'player_skip': ['webpage', 'configs'],
                    }
                },
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                # Extract relevant information
                video_data = {
                    'title': info.get('title', 'Unknown'),
                    'thumbnail': info.get('thumbnail', ''),
                    'duration': info.get('duration', 0),
                    'uploader': info.get('uploader', 'Unknown'),
                    'description': info.get('description', '')[:200],  # First 200 chars
                    'formats': []
                }
                
                # Process available formats
                formats_seen = set()
                for fmt in info.get('formats', []):
                    # Only include video formats with both video and audio or video-only with reasonable quality
                    if fmt.get('vcodec') != 'none':
                        height = fmt.get('height')
                        if height and height not in formats_seen:
                            formats_seen.add(height)
                            
                            # Determine quality label
                            quality_label = f"{height}p"
                            
                            video_data['formats'].append({
                                'quality': quality_label,
                                'height': height,
                                'format_id': fmt.get('format_id'),
                                'ext': fmt.get('ext', 'mp4'),
                                'filesize': fmt.get('filesize', 0),
                                'has_audio': fmt.get('acodec') != 'none'
                            })
                
                # Sort formats by quality (height)
                video_data['formats'].sort(key=lambda x: x['height'], reverse=True)
                
                # Add common quality options if not present
                common_qualities = [144, 240, 360, 480, 720, 1080, 1440, 2160]
                available_heights = {fmt['height'] for fmt in video_data['formats']}
                
                for quality in common_qualities:
                    if quality not in available_heights:
                        video_data['formats'].append({
                            'quality': f"{quality}p",
                            'height': quality,
                            'format_id': None,
                            'ext': 'mp4',
                            'filesize': 0,
                            'has_audio': True,
                            'available': False  # Mark as unavailable
                        })
                
                # Re-sort after adding common qualities
                video_data['formats'].sort(key=lambda x: x['height'])
                
                logger.info(f"Successfully fetched info for: {video_data['title']}")
                return video_data
                
        except Exception as e:
            logger.error(f"Error fetching video info: {str(e)}")
            raise Exception(f"Failed to fetch video information: {str(e)}")
    
    def download_video(self, url: str, quality: str = "720p", filename: Optional[str] = None) -> str:
        """
        Download video with specified quality
        
        Args:
            url: YouTube video URL
            quality: Desired quality (e.g., "720p", "1080p")
            filename: Optional custom filename
            
        Returns:
            Path to downloaded video file
        """
        max_retries = 3
        retry_count = 0
        last_error = None
        
        while retry_count < max_retries:
            try:
                # Extract height from quality string (e.g., "720p" -> 720)
                height = int(quality.replace('p', ''))
                
                # Configure download options with resilience features
                ydl_opts = {
                    'format': f'bestvideo[height<={height}]+bestaudio/best[height<={height}]/best',
                    'outtmpl': os.path.join(self.download_dir, filename if filename else '%(title)s.%(ext)s'),
                    'merge_output_format': 'mp4',
                    'quiet': False,
                    'no_warnings': False,
                    'progress_hooks': [self._progress_hook],
                    
                    # Fix 403 Forbidden errors
                    'http_headers': {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                        'Accept-Language': 'en-us,en;q=0.5',
                        'Sec-Fetch-Mode': 'navigate',
                    },
                    
                    # Use Android client for better compatibility
                    'extractor_args': {
                        'youtube': {
                            'player_client': ['android', 'web'],
                            'player_skip': ['webpage', 'configs'],
                        }
                    },
                    
                    # Enhanced retry and resilience options
                    'retries': 10,
                    'fragment_retries': 10,
                    'skip_unavailable_fragments': True,
                    'http_chunk_size': 10485760,  # 10MB chunks for better stability
                    
                    # Age-restricted video support
                    'age_limit': None,  # No age limit
                    
                    # Network resilience
                    'socket_timeout': 30,
                    'source_address': None,  # Bind to default interface
                }
                
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    logger.info(f"Starting download (attempt {retry_count + 1}/{max_retries}): {url} at {quality}")
                    info = ydl.extract_info(url, download=True)
                    
                    # Get the downloaded file path
                    downloaded_file = ydl.prepare_filename(info)
                    
                    # Verify file exists
                    if not os.path.exists(downloaded_file):
                        raise FileNotFoundError(f"Downloaded file not found: {downloaded_file}")
                    
                    logger.info(f"Download completed successfully: {downloaded_file}")
                    return downloaded_file
                    
            except Exception as e:
                last_error = e
                retry_count += 1
                
                if retry_count < max_retries:
                    # Exponential backoff: 2s, 8s, 32s
                    wait_time = min(2 ** (retry_count + 1), 60)
                    logger.warning(f"Download failed (attempt {retry_count}/{max_retries}): {str(e)}")
                    logger.info(f"Retrying in {wait_time}s...")
                    
                    import time
                    time.sleep(wait_time)
                else:
                    logger.error(f"Download failed after {max_retries} attempts: {str(e)}")
                    raise Exception(f"Failed to download video after {max_retries} attempts: {str(last_error)}")

    
    def _progress_hook(self, d):
        """Progress hook for download status"""
        if d['status'] == 'downloading':
            percent = d.get('_percent_str', '0%')
            speed = d.get('_speed_str', 'N/A')
            logger.info(f"Downloading: {percent} at {speed}")
        elif d['status'] == 'finished':
            logger.info("Download finished, now merging...")
    
    def get_best_quality_available(self, url: str) -> str:
        """
        Get the best available quality for a video
        
        Args:
            url: YouTube video URL
            
        Returns:
            Best quality string (e.g., "1080p")
        """
        try:
            info = self.get_video_info(url)
            available_formats = [fmt for fmt in info['formats'] if fmt.get('available', True)]
            
            if available_formats:
                best = max(available_formats, key=lambda x: x['height'])
                return best['quality']
            return "720p"  # Default fallback
            
        except Exception as e:
            logger.error(f"Error getting best quality: {str(e)}")
            return "720p"  # Default fallback


# Standalone usage example
if __name__ == "__main__":
    downloader = YouTubeDownloader()
    pass