import subprocess
import os
import logging
from typing import Generator

# Production-grade logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("MediaEngine")

class MediaEngine:
    """
    High-performance Media Engine for Audio-Video Processing.
    Focuses on minimum latency, zero re-encoding, and streaming pipes.
    """
    FFMPEG_PATH = "ffmpeg" # Default, can be overridden

    @classmethod
    def set_ffmpeg_path(cls, path: str):
        cls.FFMPEG_PATH = path
    @classmethod
    def extract_audio_stream(cls, video_path: str, chunk_size: int = 4096, hwaccel: str = None) -> Generator[bytes, None, None]:
        """
        Extracts audio from video and streams it via a generator.
        Output: WAV, Mono, 16kHz, S16LE.
        
        Optimization:
        - No video decoding (-vn)
        - Direct piping (pipe:1)
        - Native PCM output for zero-overhead processing
        - hwaccel: Optional hardware acceleration (e.g., 'auto', 'cuda')
        """
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Source video not found: {video_path}")

        command = [cls.FFMPEG_PATH]
        if hwaccel:
            command.extend(["-hwaccel", hwaccel])
        
        command.extend([
            "-y",
            "-hide_banner",
            "-loglevel", "error",
            "-i", video_path,
            "-vn",              # Skip video decoding
            "-acodec", "pcm_s16le", # ASR friendly format
            "-ar", "16000",     # 16kHz
            "-ac", "1",         # Mono
            "-f", "wav",        # WAV container for header safety
            "pipe:1"            # Output to stdout
        ])

        logger.info(f"Starting audio extraction pipe: {' '.join(command)}")
        
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        try:
            while True:
                chunk = process.stdout.read(chunk_size)
                if not chunk:
                    break
                yield chunk
        finally:
            process.stdout.close()
            process.wait()
            if process.returncode != 0:
                error = process.stderr.read().decode()
                logger.error(f"FFmpeg extraction failed: {error}")

    @classmethod
    def merge_audio_video(cls, video_path: str, audio_path: str, output_path: str):
        """
        Merges processed audio back into original video using stream copy.
        
        Optimization:
        - -c:v copy: Zero video re-encoding (latency win)
        - +faststart: Web-optimized (moves moov atom for quick start)
        - Single pass remuxing
        """
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video path not found: {video_path}")
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Audio path not found: {audio_path}")

        # Check for hardware acceleration availability (optional)
        # Note: Even without hwaccel, 'copy' is extremely fast as it's just I/O.
        
        command = [
            cls.FFMPEG_PATH,
            "-y",
            "-hide_banner",
            "-loglevel", "error",
            "-i", video_path,
            "-i", audio_path,
            "-map", "0:v",       # Copy all video streams
            "-map", "1:a:0",     # Take first audio stream from input 1
            "-map_metadata", "0", # Preserve original metadata
            "-c:v", "copy",      # Zero video re-encoding
            "-c:a", "aac",       # Encode audio to AAC
            "-b:a", "192k",      # High quality audio bitrate
            "-movflags", "+faststart", # Optimize for web streaming
            os.path.abspath(output_path)
        ]

        logger.info(f"Starting stream-copy merge: {' '.join(command)}")
        
        result = subprocess.run(command, capture_output=True, text=True)
        
        if result.returncode != 0:
            logger.error(f"FFmpeg merge failed: {result.stderr}")
            raise RuntimeError(f"FFmpeg merge failed: {result.stderr}")
        
        logger.info(f"Merge successful: {output_path}")
        return output_path

    @classmethod
    def slice_audio(cls, input_path: str, start: float, end: float, output_path: str):
        """
        Slices audio/video and normalizes it for the production mix.
        Ensures consistent sample rate and format to prevent 'muted' outputs in amix.
        """
        duration = end - start
        command = [
            cls.FFMPEG_PATH,
            "-y", "-hide_banner", "-loglevel", "error",
            "-ss", str(start),
            "-t", str(duration),
            "-i", input_path,
            "-acodec", "pcm_s16le", # Production quality PCM
            "-ar", "44100",        # Normalized for mixing
            "-ac", "1",            # Mono
            os.path.abspath(output_path)
        ]
        
        subprocess.run(command, check=True)
        return output_path

    @classmethod
    def extract_audio_numpy(cls, video_path: str, sr: int = 16000) -> "np.ndarray":
        """
        Extracts audio from video and returns as a NumPy array.
        Direct pipe from FFmpeg to memory.
        """
        import numpy as np
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Source video not found: {video_path}")

        command = [
            cls.FFMPEG_PATH,
            "-y", "-hide_banner", "-loglevel", "error",
            "-i", video_path,
            "-vn",
            "-acodec", "pcm_s16le",
            "-ar", str(sr),
            "-ac", "1",
            "-f", "s16le", # Raw PCM
            "pipe:1"
        ]
        
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output, error = process.communicate()
        
        if process.returncode != 0:
            logger.error(f"FFmpeg numpy extraction failed: {error.decode()}")
            raise RuntimeError(f"FFmpeg numpy extraction failed: {error.decode()}")
            
        return np.frombuffer(output, dtype=np.int16).astype(np.float32) / 32768.0

    @classmethod
    def extract_pure_audio_numpy(cls, video_path: str, sr: int = 16000) -> "np.ndarray":
        """
        Extracts PURE AUDIO from video, ignoring all subtitles and captions.
        
        CRITICAL for AI-generated videos with English captions where:
        - Captions are in English
        - But audio is in multiple languages (Hindi, French, German, etc.)
        
        This method ensures Whisper analyzes the AUDIO LANGUAGE, not caption text.
        
        Differences from extract_audio_numpy:
        - Explicitly removes all subtitle streams (-sn)
        - Ignores burned-in captions (only processes audio stream)
        - Forces audio-only analysis for language detection
        """
        import numpy as np
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Source video not found: {video_path}")

        command = [
            cls.FFMPEG_PATH,
            "-y", "-hide_banner", "-loglevel", "error",
            "-i", video_path,
            "-vn",              # No video (ignore burned-in captions)
            "-sn",              # No subtitles (ignore subtitle streams)
            "-acodec", "pcm_s16le",
            "-ar", str(sr),
            "-ac", "1",
            "-f", "s16le",      # Raw PCM
            "pipe:1"
        ]
        
        logger.info("🎵 Extracting PURE AUDIO (ignoring all captions/subtitles) for language detection")
        
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output, error = process.communicate()
        
        if process.returncode != 0:
            logger.error(f"FFmpeg pure audio extraction failed: {error.decode()}")
            raise RuntimeError(f"FFmpeg pure audio extraction failed: {error.decode()}")
            
        logger.info("✅ Pure audio extracted successfully - Whisper will analyze AUDIO LANGUAGE only")
        return np.frombuffer(output, dtype=np.int16).astype(np.float32) / 32768.0

    @classmethod
    def concat_audio_files(cls, audio_paths: list, output_path: str):
        """
        Efficiently concatenates many audio files using FFmpeg concat demuxer.
        Uses absolute paths to prevent 'File not found' errors in manifest.
        """
        import tempfile
        import os
        
        # Ensure output directory exists
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            for path in audio_paths:
                # Convert to absolute path and normalize
                abs_path = os.path.abspath(path).replace("\\", "/")
                # Escape single quotes for FFmpeg manifest
                safe_path = abs_path.replace("'", "'\\''")
                f.write(f"file '{safe_path}'\n")
            list_file = f.name
        
        try:
            command = [
                cls.FFMPEG_PATH,
                "-y", "-hide_banner", "-loglevel", "error",
                "-f", "concat",
                "-safe", "0",
                "-i", list_file,
                "-c", "copy",
                os.path.abspath(output_path)
            ]
            # Use subprocess without shell to avoid path escaping issues
            subprocess.run(command, check=True)
        finally:
            if os.path.exists(list_file):
                try:
                    os.remove(list_file)
                except:
                    pass
        return output_path

    @classmethod
    def merge_complex(cls, video_path: str, tts_audio_path: str, background_audio_path: str, output_path: str, bg_volume: float = 0.3):
        """
        One-pass merge with Audio Ducking.
        Lowers background music when speech is present using the 'sidechain' filter approach.
        """
        command = [
            cls.FFMPEG_PATH,
            "-y", "-hide_banner", "-loglevel", "error",
            "-i", video_path,
            "-i", tts_audio_path,
            "-i", background_audio_path,
            "-filter_complex",
            # Logic: 
            # 1. Take Background [2:a] and scale it to base level.
            # 2. Use TTS [1:a] as a control signal to duck Background.
            # 3. Mix the ducked BG with the TTS.
            f"[2:a]volume={bg_volume}[bg_vol];" +
            "[1:a]asplit[v_mix][v_side];" +
            "[bg_vol][v_side]sidechaincompress=threshold=0.1:ratio=2:release=500:attack=10[bg_ducked];" +
            "[v_mix][bg_ducked]amix=inputs=2:duration=longest[aout]",
            "-map", "0:v",
            "-map", "[aout]",
            "-map_metadata", "0",
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            "-movflags", "+faststart",
            os.path.abspath(output_path)
        ]
        
        logger.info(f"Starting complex merge with ducking...")
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Complex merge with ducking failed: {result.stderr}")
        return output_path

    @staticmethod
    def get_probe_info(file_path: str) -> dict:
        """Helper to get media info using ffprobe."""
        import json
        command = [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            file_path
        ]
        result = subprocess.run(command, capture_output=True, text=True)
        return json.loads(result.stdout)

# Use case example
if __name__ == "__main__":
    # This is a stub for testing
    # media = MediaEngine()
    # chunks = list(media.extract_audio_stream("input.mp4"))
    # print(f"Extracted {len(chunks)} chunks")
    pass
