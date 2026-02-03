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
        save_at = os.path.join(settings.BASE_DIR, "audio_data")
        os.makedirs(save_at, exist_ok=True)

        # Use a local temporary folder to avoid conflicts
        temp_folder = os.path.join(settings.TEMP_DIR, "audio_separate")
        if os.path.exists(temp_folder):
            shutil.rmtree(temp_folder)

        os.makedirs(temp_folder, exist_ok=True)

        # Check if audio-separator is available
        check_cmd = "audio-separator --version"
        if subprocess.call(check_cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) != 0:
            logger.error("Audio Separator tool not found. Please install if using background recovery.")
            return None, None

        # Run the audio separator command
        command = f'audio-separator "{source_path}" --model_filename UVR-MDX-NET-Inst_HQ_3.onnx --output_dir "{temp_folder}"'
        logger.info(f"Running separation: {command}")
        
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        vocal_path, noise_path = None, None

        if result.returncode == 0:  # Check if the command was successful
            for file_name in os.listdir(temp_folder):
                if "instrumental" in file_name.lower():
                    noise_path = save_processed_file(file_name, temp_folder, save_at, source_path, "noise")

                if "vocals" in file_name.lower():
                    vocal_path = save_processed_file(file_name, temp_folder, save_at, source_path, "vocals")

            # Clean up temporary folder after processing
            shutil.rmtree(temp_folder)
        else:
            logger.error(f"Audio separation failed: {result.stderr}")

        return vocal_path, noise_path

    except Exception as e:
        logger.error(f"An error occurred during separation: {e}")
        return None, None
