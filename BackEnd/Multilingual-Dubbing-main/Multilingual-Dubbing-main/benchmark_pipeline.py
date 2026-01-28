import time
import os
from media_engine import MediaEngine

def run_benchmark():
    # Use the discovered ffmpeg path in the venv
    ffmpeg_path = r"c:\Users\sweth\OneDrive\Desktop\tech\Techgium-AutoDub\BackEnd\Multilingual-Dubbing-main\Multilingual-Dubbing-main\venv311\Scripts\static_ffmpeg.exe"
    MediaEngine.set_ffmpeg_path(ffmpeg_path)
    
    video_path = r"c:\Users\sweth\OneDrive\Desktop\tech\Techgium-AutoDub\BackEnd\Multilingual-Dubbing-main\Multilingual-Dubbing-main\temp_uploads\e7ec9309-6c70-49af-9d39-e088e58ffabf_samplevideosharan.mp4"
    if not os.path.exists(video_path):
        print(f"Test video not found at {video_path}")
        return

    engine = MediaEngine()

    print("--- Phase 1: Streaming Audio Extraction ---")
    start_time = time.time()
    chunk_count = 0
    total_bytes = 0
    
    # We write the first 5 seconds to a file just to verify it's valid, but we stream the rest
    for chunk in engine.extract_audio_stream(video_path):
        chunk_count += 1
        total_bytes += len(chunk)
    
    extraction_time = time.time() - start_time
    print(f"Extracted {total_bytes / 1024 / 1024:.2f} MB in {extraction_time:.4f} seconds")
    print(f"Average throughput: {total_bytes / 1024 / 1024 / extraction_time:.2f} MB/s")

    print("\n--- Phase 2: Stream-Copy Merging ---")
    # For testing merge, we need a dummy audio file. We'll use the one we just (conceptually) extracted
    # Let's actually save the extraction to a temp file for this test
    temp_audio = "temp_extracted.wav"
    with open(temp_audio, "wb") as f:
        for chunk in engine.extract_audio_stream(video_path):
            f.write(chunk)
    
    output_video = "benchmark_output.mp4"
    start_time = time.time()
    engine.merge_audio_video(video_path, temp_audio, output_video)
    merge_time = time.time() - start_time
    
    print(f"Merged audio and video in {merge_time:.4f} seconds (Stream Copy)")
    
    if os.path.exists(output_video):
        size = os.path.getsize(output_video)
        print(f"Output video size: {size / 1024 / 1024:.2f} MB")
        os.remove(output_video)
    
    if os.path.exists(temp_audio):
        os.remove(temp_audio)

if __name__ == "__main__":
    run_benchmark()
