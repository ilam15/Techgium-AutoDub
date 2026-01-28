
import os
import shutil
import time

def cleanup_unnecessary_files(keep_files=None, directories=None):
    """
    Cleans up files in the specified directories, excluding those in keep_files.
    
    Args:
        keep_files (list): List of absolute paths of files to preserve.
        directories (list): List of directory paths to clean.
    """
    if keep_files is None:
        keep_files = []
    
    if directories is None:
        # Default directories specified by the user
        # Note: 'audio' might be 'audio_data' or actual 'audio' folder. 
        # Using 'audio', 'dummy', 'generated_subtitle' based on request.
        directories = ['audio', 'dummy', 'generated_subtitle']

    # Normalize keep_files to absolute paths for comparison
    keep_files_abs = set(os.path.abspath(f) for f in keep_files if f)
    
    print("Starting cleanup process...")
    print(f"Preserving files: {keep_files_abs}")

    for dir_name in directories:
        # Resolve to absolute path relative to this script if needed, 
        # assuming this script runs from the project root.
        if not os.path.isabs(dir_name):
            dir_path = os.path.abspath(dir_name)
        else:
            dir_path = dir_name

        if not os.path.exists(dir_path):
            print(f"Directory not found, skipping: {dir_path}")
            continue

        print(f"Cleaning directory: {dir_path}")
        
        # Walk top-down
        for root, dirs, files in os.walk(dir_path):
            for file in files:
                file_path = os.path.join(root, file)
                abs_path = os.path.abspath(file_path)
                
                if abs_path in keep_files_abs:
                    print(f"Skipping preserved file: {file_path}")
                    continue
                
                try:
                    os.remove(file_path)
                    # print(f"Deleted: {file_path}")
                except Exception as e:
                    print(f"Failed to delete {file_path}: {e}")
            
            # Should we remove empty subdirectories? 
            # The user didn't explicitly ask, but 'dummy' folder creates subfolders for segments.
            # It's cleaner to remove them.
            for d in dirs:
                dir_full_path = os.path.join(root, d)
                # Check if directory contains any kept files (recursively is hard here without bottom-up)
                # But os.walk is generating dirs.
                # A simpler approach for dirs is to use shutil.rmtree if we know it contains nothing to keep.
                # But we might have kept files inside.
                pass

        # Cleanup empty directories (bottom-up is better for this)
        for root, dirs, files in os.walk(dir_path, topdown=False):
            for name in dirs:
                d_path = os.path.join(root, name)
                try:
                    # rmdir only works if empty
                    os.rmdir(d_path)
                except OSError:
                    # Directory not empty (likely contains kept files)
                    pass

    print("Cleanup completed.")

if __name__ == "__main__":
    # For testing manually
    cleanup_unnecessary_files()
