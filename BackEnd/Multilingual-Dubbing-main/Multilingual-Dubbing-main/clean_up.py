import os
import shutil
import glob
from pathlib import Path
from typing import Optional, List
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_latest_output_video(output_dir: str = ".") -> Optional[str]:
    """
    Find the most recently created output video file.
    
    Args:
        output_dir: Directory to search for output videos
        
    Returns:
        Path to the latest output video or None
    """
    output_pattern = os.path.join(output_dir, "output_*.mp4")
    output_files = glob.glob(output_pattern)
    
    if not output_files:
        return None
    
    # Sort by modification time, newest first
    latest_file = max(output_files, key=os.path.getmtime)
    return latest_file


def get_directory_size(directory: str) -> int:
    """Calculate total size of directory in bytes."""
    total_size = 0
    try:
        for dirpath, dirnames, filenames in os.walk(directory):
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                if os.path.exists(filepath):
                    total_size += os.path.getsize(filepath)
    except Exception as e:
        logger.warning(f"Error calculating size for {directory}: {e}")
    return total_size


def format_size(bytes_size: int) -> str:
    """Format bytes to human-readable size."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.2f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.2f} TB"


def cleanup_directory(directory: str, keep_files: set = None) -> dict:
    """
    Clean up a directory, optionally preserving specific files.
    
    Args:
        directory: Path to directory to clean
        keep_files: Set of absolute paths to preserve
        
    Returns:
        Dictionary with cleanup statistics
    """
    if keep_files is None:
        keep_files = set()
    
    stats = {
        'files_deleted': 0,
        'dirs_deleted': 0,
        'bytes_freed': 0,
        'errors': 0
    }
    
    if not os.path.exists(directory):
        logger.info(f"Directory not found, skipping: {directory}")
        return stats
    
    # Calculate size before cleanup
    size_before = get_directory_size(directory)
    
    logger.info(f"Cleaning directory: {directory}")
    
    # Delete files (top-down)
    for root, dirs, files in os.walk(directory):
        for file in files:
            file_path = os.path.join(root, file)
            abs_path = os.path.abspath(file_path)
            
            if abs_path in keep_files:
                logger.info(f"Preserving: {file_path}")
                continue
            
            try:
                file_size = os.path.getsize(file_path)
                os.remove(file_path)
                stats['files_deleted'] += 1
                stats['bytes_freed'] += file_size
            except Exception as e:
                logger.error(f"Failed to delete {file_path}: {e}")
                stats['errors'] += 1
    
    # Remove empty directories (bottom-up)
    for root, dirs, files in os.walk(directory, topdown=False):
        for dir_name in dirs:
            dir_path = os.path.join(root, dir_name)
            try:
                if not os.listdir(dir_path):  # Check if empty
                    os.rmdir(dir_path)
                    stats['dirs_deleted'] += 1
            except OSError:
                pass  # Directory not empty or other error
    
    return stats


def cleanup_old_output_videos(output_dir: str = ".", keep_latest: bool = True) -> dict:
    """
    Remove old output videos, optionally keeping the latest one.
    
    Args:
        output_dir: Directory containing output videos
        keep_latest: If True, keep the most recent output video
        
    Returns:
        Dictionary with cleanup statistics
    """
    stats = {
        'files_deleted': 0,
        'bytes_freed': 0,
        'latest_kept': None
    }
    
    output_pattern = os.path.join(output_dir, "output_*.mp4")
    output_files = glob.glob(output_pattern)
    
    if not output_files:
        logger.info("No output videos found")
        return stats
    
    # Find latest file
    latest_file = None
    if keep_latest:
        latest_file = max(output_files, key=os.path.getmtime)
        stats['latest_kept'] = latest_file
        logger.info(f"Keeping latest output: {latest_file}")
    
    # Delete all others
    for video_file in output_files:
        if keep_latest and video_file == latest_file:
            continue
        
        try:
            file_size = os.path.getsize(video_file)
            os.remove(video_file)
            stats['files_deleted'] += 1
            stats['bytes_freed'] += file_size
            logger.info(f"Deleted old output: {video_file}")
        except Exception as e:
            logger.error(f"Failed to delete {video_file}: {e}")
    
    return stats


def cleanup_all_temporary_files(keep_latest_output: bool = True, preserve_files: List[str] = None) -> dict:
    """
    Comprehensive cleanup of all temporary files and directories.
    
    Args:
        keep_latest_output: If True, preserve the most recent output video
        preserve_files: Additional files to preserve (absolute paths)
        
    Returns:
        Dictionary with comprehensive cleanup statistics
    """
    logger.info("=" * 60)
    logger.info("Starting comprehensive cleanup process...")
    logger.info("=" * 60)
    
    # Directories to clean
    temp_directories = [
        'audio',
        'audio_data',
        'temp_uploads',
        'subtitle_audio',
        'TTS_DUB',
        'temp',
        'temp_downloads',
        'dummy', 
        'generated_subtitle'
    ]
    
    # Build set of files to preserve
    keep_files = set()
    if preserve_files:
        keep_files.update(os.path.abspath(f) for f in preserve_files if f)
    
    # Add latest output video to preserve list
    if keep_latest_output:
        latest_output = get_latest_output_video()
        if latest_output:
            keep_files.add(os.path.abspath(latest_output))
            logger.info(f"Will preserve latest output: {latest_output}")
    
    # Overall statistics
    total_stats = {
        'total_files_deleted': 0,
        'total_dirs_deleted': 0,
        'total_bytes_freed': 0,
        'total_errors': 0,
        'directory_stats': {}
    }
    
    # Clean each directory
    for directory in temp_directories:
        if os.path.exists(directory):
            logger.info(f"\n📁 Processing: {directory}")
            stats = cleanup_directory(directory, keep_files)
            total_stats['directory_stats'][directory] = stats
            total_stats['total_files_deleted'] += stats['files_deleted']
            total_stats['total_dirs_deleted'] += stats['dirs_deleted']
            total_stats['total_bytes_freed'] += stats['bytes_freed']
            total_stats['total_errors'] += stats['errors']
            
            logger.info(f"   Files deleted: {stats['files_deleted']}")
            logger.info(f"   Space freed: {format_size(stats['bytes_freed'])}")
    
    # Clean old output videos
    logger.info(f"\n📹 Processing output videos...")
    output_stats = cleanup_old_output_videos(keep_latest=keep_latest_output)
    total_stats['output_videos_deleted'] = output_stats['files_deleted']
    total_stats['total_files_deleted'] += output_stats['files_deleted']
    total_stats['total_bytes_freed'] += output_stats['bytes_freed']
    total_stats['latest_output_kept'] = output_stats['latest_kept']
    
    # Clean temporary files in root
    temp_files = ['temp.txt', 'temp.wav']
    for temp_file in temp_files:
        if os.path.exists(temp_file):
            try:
                file_size = os.path.getsize(temp_file)
                os.remove(temp_file)
                total_stats['total_files_deleted'] += 1
                total_stats['total_bytes_freed'] += file_size
                logger.info(f"Deleted temporary file: {temp_file}")
            except Exception as e:
                logger.error(f"Failed to delete {temp_file}: {e}")
    
    # Print summary
    logger.info("\n" + "=" * 60)
    logger.info("CLEANUP SUMMARY")
    logger.info("=" * 60)
    logger.info(f"✅ Total files deleted: {total_stats['total_files_deleted']}")
    logger.info(f"✅ Total directories deleted: {total_stats['total_dirs_deleted']}")
    logger.info(f"✅ Total space freed: {format_size(total_stats['total_bytes_freed'])}")
    if total_stats['total_errors'] > 0:
        logger.warning(f"⚠️  Errors encountered: {total_stats['total_errors']}")
    if total_stats['latest_output_kept']:
        logger.info(f"📦 Latest output preserved: {total_stats['latest_output_kept']}")
    logger.info("=" * 60)
    
    return total_stats


if __name__ == "__main__":
    # Run comprehensive cleanup when executed directly
    cleanup_all_temporary_files(keep_latest_output=True)
