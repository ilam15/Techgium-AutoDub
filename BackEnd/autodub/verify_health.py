import sys
import os

# Add local path to sys.path
sys.path.append(os.getcwd())

def check_system():
    print("--- AutoDub System Audit ---")
    
    # 1. Check Imports
    try:
        from src.tasks import (
            separation_task, 
            analysis_task, 
            synthesis_task, 
            merge_final_video_task
        )
        print("[OK] All tasks imported successfully.")
    except Exception as e:
        print(f"[FAIL] Task import failed: {e}")
        return

    # 2. Check Celery Registry
    from src.core.celery_app import celery_app
    registered_tasks = celery_app.tasks.keys()
    required = [
        "src.tasks.separation_task",
        "src.tasks.analysis_task",
        "src.tasks.synthesis_task",
        "src.tasks.merge_final_video_task"
    ]
    
    all_registered = True
    for task in required:
        if task in registered_tasks:
            print(f"[OK] Task Registered: {task}")
        else:
            print(f"[MISSING] Task NOT registered: {task}")
            all_registered = False
            
    # 3. Check FFmpeg
    import shutil
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path:
        print(f"[OK] FFmpeg found at: {ffmpeg_path}")
    else:
        # Check if static-ffmpeg is installed (MediaEngine logic)
        try:
            from static_ffmpeg import run
            print("[OK] static-ffmpeg discovered.")
        except:
            print("[WARN] FFmpeg not found in PATH or static-ffmpeg.")

    # 4. Check Redis Connectivity
    import redis
    try:
        r = redis.Redis(host='localhost', port=6379, db=0)
        r.ping()
        print("[OK] Redis connection successful.")
    except Exception as e:
        print(f"[FAIL] Redis Connection failed: {e}")

    print("\nSystem Audit Complete.")
    if all_registered:
        print("RESULT: Backend Logic is VALID and READY for launch.")
    else:
        print("RESULT: Backend Logic has REGISTRATION ISSUES.")

if __name__ == "__main__":
    check_system()
