"""
Diagnostic script to check video file streams and help debug FFmpeg merge issues
"""

import subprocess
import json
import os
import sys

def get_probe_info(file_path: str) -> dict:
    """Get media info using ffprobe."""
    command = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        file_path
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"❌ FFprobe failed: {result.stderr}")
        return {}
    return json.loads(result.stdout)

def analyze_video_file(file_path: str):
    """Analyze a video file and print detailed stream information."""
    print(f"\n{'='*70}")
    print(f"Analyzing: {os.path.basename(file_path)}")
    print(f"{'='*70}")
    
    if not os.path.exists(file_path):
        print(f"❌ File not found: {file_path}")
        return
    
    file_size = os.path.getsize(file_path)
    print(f"\n📁 File Info:")
    print(f"   Path: {file_path}")
    print(f"   Size: {file_size:,} bytes ({file_size/1024/1024:.2f} MB)")
    
    if file_size == 0:
        print(f"   ⚠️  WARNING: File is empty!")
        return
    
    # Probe the file
    probe_info = get_probe_info(file_path)
    
    if not probe_info:
        print(f"\n❌ Could not probe file. It may be corrupted.")
        return
    
    # Format info
    format_info = probe_info.get('format', {})
    print(f"\n📺 Format Info:")
    print(f"   Format: {format_info.get('format_name', 'Unknown')}")
    print(f"   Duration: {float(format_info.get('duration', 0)):.2f} seconds")
    print(f"   Bit rate: {int(format_info.get('bit_rate', 0)):,} bps")
    
    # Stream info
    streams = probe_info.get('streams', [])
    print(f"\n🎬 Streams ({len(streams)} total):")
    
    video_streams = []
    audio_streams = []
    other_streams = []
    
    for i, stream in enumerate(streams):
        codec_type = stream.get('codec_type', 'unknown')
        codec_name = stream.get('codec_name', 'unknown')
        
        if codec_type == 'video':
            video_streams.append(stream)
            width = stream.get('width', 'N/A')
            height = stream.get('height', 'N/A')
            fps = stream.get('r_frame_rate', 'N/A')
            print(f"   [{i}] VIDEO: {codec_name}, {width}x{height}, {fps} fps")
        elif codec_type == 'audio':
            audio_streams.append(stream)
            sample_rate = stream.get('sample_rate', 'N/A')
            channels = stream.get('channels', 'N/A')
            print(f"   [{i}] AUDIO: {codec_name}, {sample_rate} Hz, {channels} channels")
        else:
            other_streams.append(stream)
            print(f"   [{i}] {codec_type.upper()}: {codec_name}")
    
    # Summary
    print(f"\n📊 Summary:")
    print(f"   Video streams: {len(video_streams)} {'✅' if video_streams else '❌'}")
    print(f"   Audio streams: {len(audio_streams)} {'✅' if audio_streams else '❌'}")
    print(f"   Other streams: {len(other_streams)}")
    
    # Recommendations
    print(f"\n💡 Recommendations:")
    if not video_streams:
        print(f"   ⚠️  NO VIDEO STREAM FOUND!")
        print(f"   This file is audio-only or corrupted.")
        print(f"   FFmpeg will fail with: 'Stream map 0:v matches no streams'")
        print(f"   Solution: Use optional mapping '-map 0:v?' or download with video format")
    elif not audio_streams:
        print(f"   ⚠️  NO AUDIO STREAM FOUND!")
        print(f"   This is a video-only file.")
    else:
        print(f"   ✅ File has both video and audio streams - should work fine!")
    
    return probe_info

def main():
    """Main function to analyze video files."""
    print(f"\n{'#'*70}")
    print("Video File Stream Analyzer")
    print(f"{'#'*70}")
    
    # Check if file path provided
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        analyze_video_file(file_path)
    else:
        # Analyze all files in temp_uploads directory
        temp_dir = "temp_uploads"
        if not os.path.exists(temp_dir):
            print(f"\n❌ Directory not found: {temp_dir}")
            print(f"\nUsage: python diagnose_video.py <video_file_path>")
            return
        
        video_files = [f for f in os.listdir(temp_dir) if f.endswith(('.mp4', '.mkv', '.avi', '.mov', '.webm'))]
        
        if not video_files:
            print(f"\n❌ No video files found in {temp_dir}")
            print(f"\nUsage: python diagnose_video.py <video_file_path>")
            return
        
        print(f"\nFound {len(video_files)} video file(s) in {temp_dir}")
        
        for video_file in video_files:
            file_path = os.path.join(temp_dir, video_file)
            analyze_video_file(file_path)
    
    print(f"\n{'#'*70}")
    print("Analysis Complete")
    print(f"{'#'*70}\n")

if __name__ == "__main__":
    main()
