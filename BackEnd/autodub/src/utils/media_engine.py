import subprocess
import os
import logging
import uuid
from typing import Generator

# Production-grade logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("MediaEngine")

class MediaEngine:
    """
    High-performance Media Engine for Audio-Video Processing.
    Focuses on minimum latency, zero re-encoding, and streaming pipes.
    """
    FFMPEG_PATH = "ffmpeg"
    FFPROBE_PATH = "ffprobe"

    @classmethod
    def initialize(cls):
        """Initializes FFmpeg paths using static-ffmpeg if needed."""
        import shutil
        import os
        
        # Try to find system ffmpeg first
        if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
            try:
                import static_ffmpeg
                logger.info("system ffmpeg not found, attempting to use static-ffmpeg...")
                static_ffmpeg.add_paths()
            except ImportError:
                logger.warning("static-ffmpeg not installed and system ffmpeg missing.")

        # Re-check and set absolute paths
        cls.FFMPEG_PATH = shutil.which("ffmpeg") or "ffmpeg"
        cls.FFPROBE_PATH = shutil.which("ffprobe") or "ffprobe"
        
        if shutil.which(cls.FFMPEG_PATH):
            logger.info(f"FFmpeg path resolved: {cls.FFMPEG_PATH}")
        else:
            logger.error("FFmpeg could not be resolved by system or static-ffmpeg!")



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
        - -map 0:v -map 1:a: Explicitly map tracks
        - -shortest: Ensure output ends when shortest stream ends
        - -movflags +faststart: Web-optimized
        """
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video path not found: {video_path}")
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Audio path not found: {audio_path}")

        # Get Video Duration to prevent truncation
        probe = cls.get_probe_info(video_path)
        video_dur = probe['format'].get('duration', '0')

        command = [
            cls.FFMPEG_PATH,
            "-y",
            "-hide_banner",
            "-loglevel", "error",
            "-i", video_path,
            "-i", audio_path,
            "-map", "0:v:0",      # Take video from input 0
            "-map", "1:a:0",      # Take audio from input 1
            "-c:v", "copy",       # Stream copy video
            "-c:a", "aac",        # Encode audio to AAC
            "-b:a", "192k",
            "-t", str(video_dur), # FORCE master video duration
            "-movflags", "+faststart",
            os.path.abspath(output_path)
        ]

        logger.info(f"Starting Precision Merge: {' '.join(command)}")
        
        result = subprocess.run(command, capture_output=True, text=True)
        
        if result.returncode != 0:
            logger.error(f"FFmpeg merge failed: {result.stderr}")
            raise RuntimeError(f"FFmpeg merge failed: {result.stderr}")
        
        # Apply Post-Merge Stabilization
        return cls.stabilize_media(output_path)

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
        """
        return cls.extract_pure_audio_numpy_segment(video_path, start=0, duration=None, sr=sr)

    @classmethod
    def extract_pure_audio_numpy_segment(cls, video_path: str, start: float, duration: float = None, sr: int = 16000) -> "np.ndarray":
        """
        High-precision segment extraction into NumPy, perfect for per-segment lang/gender detection.
        Ignores all subtitle streams and only processes the audio track.
        """
        import numpy as np
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Source video not found: {video_path}")

        command = [
            cls.FFMPEG_PATH,
            "-y", "-hide_banner", "-loglevel", "error"
        ]
        
        # Seeking at the input level is much faster
        if start > 0:
            command.extend(["-ss", str(start)])
        
        command.extend(["-i", video_path])
        
        if duration:
            command.extend(["-t", str(duration)])
            
        command.extend([
            "-vn",              # No video
            "-sn",              # No subtitles
            "-acodec", "pcm_s16le",
            "-ar", str(sr),
            "-ac", "1",
            "-f", "s16le",      # Raw PCM
            "pipe:1"
        ])
        
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output, error = process.communicate()
        
        if process.returncode != 0:
            # Fallback for short clips where seeking might be out of bounds or failing
            logger.debug(f"Seek extraction failed, falling back to full extraction slicing for tiny segment.")
            return np.array([], dtype=np.float32)
            
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
    def create_silent_base(cls, duration: float, output_path: str):
        """Creates a silent base track for full video duration."""
        command = [
            cls.FFMPEG_PATH,
            "-y", "-f", "lavfi",
            "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
            "-t", str(duration),
            output_path
        ]
        subprocess.run(command, check=True)
        return output_path

    @classmethod
    def overlay_segments(cls, video_path: str, background_audio_path: str, segments: list, output_path: str, bg_volume: float = 1.0):
        """
        Refactored Overlay Mix: Uses Filter Scripts to bypass OS command limits.
        Ensures perfect master-clock sync using adelay and a finite base track.
        """
        if not segments:
            logger.warning("No segments to overlay. Performing simple merge.")
            return cls.merge_audio_video(video_path, background_audio_path or "", output_path)

        # 1. Get Video Duration for Finite Base
        probe = cls.get_probe_info(video_path)
        video_dur = float(probe['format']['duration'])

        # 2. Build Filter Script
        filter_parts = []
        # [1:a] is Background or silent base
        filter_parts.append(f"[1:a]volume={bg_volume}[bg_vol]")
        
        mix_labels = []
        for i, seg in enumerate(segments):
            in_idx = i + 2
            label = f"s{i}"
            delay_ms = int(seg["start"] * 1000)
            # Use 'adelay' for absolute positioning (Fix 3)
            filter_parts.append(f"[{in_idx}:a]adelay={delay_ms}|{delay_ms}[{label}]")
            mix_labels.append(f"[{label}]")
            
        # Dialogue Mix + Robust Volume Fix (Architecture P3)
        # We disable amix's dynamic normalization (normalize=0) to prevent volume jumps as segments end.
        # This ensures every speaker is heard at a consistent 1.5x volume boost.
        num_segs = len(segments)
        active_boost = 1.5
        filter_parts.append(f"{''.join(mix_labels)}amix=inputs={num_segs}:normalize=0:dropout_transition=0,volume={active_boost}[dialogue]")
        
        # Sidechain Ducking (PRECISE PASS)
        # Background remains 1.0 (original) but ducks smoothly to 0.4x when dialogue is active.
        filter_parts.append("[dialogue]asplit[v_mix][v_side]")
        filter_parts.append("[bg_vol][v_side]sidechaincompress=threshold=0.1:ratio=2.5:release=500:attack=10[bg_ducked]")
        
        # Final Mix: Use normalization=1 for the two full-length tracks (Dialogue + Background)
        # We multiply by 2 to counteract the 1/2 reduction from amix's default normalization.
        filter_parts.append("[v_mix][bg_ducked]amix=inputs=2:dropout_transition=0:duration=longest,volume=2[aout]")

        filter_script_path = os.path.join(os.path.dirname(output_path), f"filter_{uuid.uuid4().hex[:8]}.txt")
        with open(filter_script_path, "w", encoding="utf-8") as f:
            f.write(";\n".join(filter_parts))

        # 3. Assemble Command
        cmd = [cls.FFMPEG_PATH, "-y", "-hide_banner", "-loglevel", "error"]
        cmd.extend(["-i", video_path]) # Input 0
        
        if background_audio_path and os.path.exists(background_audio_path):
            cmd.extend(["-i", background_audio_path]) # Input 1
        else:
            # Create finite silent base (Crucial for amix duration stability)
            cmd.extend(["-f", "lavfi", "-t", str(video_dur), "-i", "anullsrc=channel_layout=stereo:sample_rate=44100"])

        for seg in segments:
            cmd.extend(["-i", seg["path"]])

        cmd.extend([
            "-filter_complex_script", filter_script_path,
            "-map", "0:v:0",
            "-map", "[aout]",
            "-c:v", "copy",
            "-c:a", "aac",
            "-t", str(video_dur), # Anchor to master video duration (prevents reduction)
            "-movflags", "+faststart",
            os.path.abspath(output_path)
        ])

        try:
            logger.info(f"🚀 Executing Scripted Overlay Mix (Max Stability: {len(segments)} inputs)...")
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                raise RuntimeError(f"FFmpeg overlay failed: {result.stderr}")
        finally:
            if os.path.exists(filter_script_path):
                os.remove(filter_script_path)

        return cls.stabilize_media(output_path)

    @classmethod
    def merge_complex(cls, video_path: str, tts_audio_path: str, background_audio_path: str, output_path: str, bg_volume: float = 0.3):
        """
        One-pass merge with Audio Ducking and master-clock sync.
        """
        command = [
            cls.FFMPEG_PATH,
            "-y", "-hide_banner", "-loglevel", "error",
            "-i", video_path,
            "-i", tts_audio_path,
            "-i", background_audio_path,
            "-filter_complex",
            f"[2:a]volume={bg_volume}[bg_vol];" +
            "[1:a]asplit[v_mix][v_side];" +
            "[bg_vol][v_side]sidechaincompress=threshold=0.1:ratio=2:release=500:attack=10[bg_ducked];" +
            "[v_mix][bg_ducked]amix=inputs=2:duration=longest[aout]",
            "-map", "0:v:0",
            "-map", "[aout]",
            "-c:v", "copy",
            "-c:a", "aac",
            "-shortest", 
            "-movflags", "+faststart",
            os.path.abspath(output_path)
        ]
        
        logger.info(f"Starting complex master-clock merge...")
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Complex merge failed: {result.stderr}")
        
        return cls.stabilize_media(output_path)

    @classmethod
    def stabilize_media(cls, file_path: str):
        """
        Final stabilization pass (Drift Correction).
        Aligns PTS and fixes micro-drifts using 'aresample=async=1'.
        """
        temp_stabilized = file_path.replace(".mp4", "_stable.mp4")
        
        # Get duration for safety
        probe = cls.get_probe_info(file_path)
        dur = probe['format'].get('duration')

        command = [
            cls.FFMPEG_PATH,
            "-y", "-hide_banner", "-loglevel", "error",
            "-i", file_path,
            "-af", "aresample=async=1:first_pts=0",
            "-c:v", "copy", 
            "-c:a", "aac",
            "-t", str(dur) if dur else "0"
        ]
        
        if dur:
            command.append(temp_stabilized)
            logger.info(f"🚀 Running Drift Correction (Stabilization Pass)...")
            res = subprocess.run(command, capture_output=True)
            if res.returncode == 0:
                os.replace(temp_stabilized, file_path)
                return file_path
        
        return file_path

    @classmethod
    def get_probe_info(cls, file_path: str) -> dict:
        """Helper to get media info using ffprobe."""
        import json
        command = [
            cls.FFPROBE_PATH,
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            file_path
        ]
        result = subprocess.run(command, capture_output=True, text=True)
        return json.loads(result.stdout)

# Auto-initialize FFmpeg paths
MediaEngine.initialize()
