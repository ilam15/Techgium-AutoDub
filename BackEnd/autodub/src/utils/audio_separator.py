import os
import shutil
import subprocess
from pydub import AudioSegment
from src.core.config import settings
from src.core.logger import logger

def save_processed_file(file_name, temp_folder, save_at, source_path, file_type):
    try:
        source_base_name = os.path.splitext(os.path.basename(source_path))[0]
        output_file_name = f"{source_base_name}_{file_type}.wav"
        output_file_path = os.path.join(save_at, output_file_name)

        input_file_path = os.path.join(temp_folder, file_name)
        if input_file_path.endswith(".flac"):
            # Convert FLAC to WAV
            audio = AudioSegment.from_file(input_file_path, format="flac")
            audio.export(output_file_path, format="wav")
            logger.info(f"Saved {file_type} to {output_file_path}")
        else:
            shutil.copy(input_file_path, output_file_path)
            logger.info(f"Copied {file_type} to {output_file_path}")

        return output_file_path
    except Exception as e:
        logger.error(f"Error processing file {file_name}: {e}")
        return None

def separate_audio(source_path):
    try:
        from src.app import model_manager
        
        save_at = os.path.join(settings.BASE_DIR, "audio_data")
        os.makedirs(save_at, exist_ok=True)

        # Use a unique temporary folder per request to avoid race conditions in parallel mode
        import uuid
        unique_id = uuid.uuid4().hex[:8]
        temp_folder = os.path.join(settings.TEMP_DIR, f"audio_separate_{unique_id}")
        os.makedirs(temp_folder, exist_ok=True)

        logger.info(f"Refactored: Starting Native Separation for {source_path}")
        
        # Initialize the native separator via Singleton (Saves RAM/OOM)
        separator = model_manager.get_separator()
        separator.output_dir = temp_folder # Redirect output for this task
        
        # Load the specific model
        model_name = "UVR-MDX-NET-Inst_HQ_3.onnx"
        logger.info(f"Loading model: {model_name}")
        separator.load_model(model_name)
        
        # Perform separation
        output_files = separator.separate(source_path)
        logger.info(f"Native separation finished. Produced: {output_files}")
        
        vocal_path, noise_path = None, None

        # The 'separate' method returns a list of produced filenames (not full paths)
        for file_name in output_files:
            file_name_lower = file_name.lower()
            if "instrumental" in file_name_lower or "(instrumental)" in file_name_lower:
                noise_path = save_processed_file(file_name, temp_folder, save_at, source_path, "noise")

            if "vocals" in file_name_lower or "(vocals)" in file_name_lower:
                vocal_path = save_processed_file(file_name, temp_folder, save_at, source_path, "vocals")

        # Cleanup
        try:
            shutil.rmtree(temp_folder)
        except:
            pass

        return vocal_path, noise_path

    except Exception as e:
        logger.error(f"Native separation failed with exception: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None, None
