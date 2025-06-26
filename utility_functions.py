import os
import re
import sys
import glob
import platform
import subprocess

def get_unique_filename(path):
    # Checks if filename exists, appends number if it does
    if not os.path.exists(path):
        return path
    base, ext = os.path.splitext(path)
    counter = 1
    while True:
        new_path = f"{base} ({counter}){ext}"
        if not os.path.exists(new_path):
            return new_path
        counter += 1

def open_file_for_editing(filepath):
    # Opens a file in the default system editor
    # NOTE: Only tested WSL/Windows, others are from copilot, hope they work! 
    print(f"Attempting to open '{filepath}' for manual editing...")
    try:
        is_wsl = 'microsoft' in platform.uname().release.lower() or 'wsl' in platform.uname().release.lower()
        if sys.platform == "win32":
            os.startfile(filepath)
        elif is_wsl:
            # In WSL, use windows to open file, not VIM
            absolute_wsl_path = os.path.abspath(filepath)
            windows_path = subprocess.check_output(['wslpath', '-w', absolute_wsl_path]).strip().decode('utf-8')
            subprocess.call(['explorer.exe', windows_path])
        elif sys.platform == "darwin": # macOS
            subprocess.call(["open", filepath])
        else: # Linux, WSL, etc.
            subprocess.call(["xdg-open", filepath])
    except Exception as e:
        print(f"\n!!! Could not automatically open the file. Error: {e} !!!!")
        print("Open the file manually to make edits.")

def reduce_text_numerics(text):
    # Replaces all digits in a string with a placeholder for pattern matching
    return re.sub(r'\d+', '_NUM_', text)

def stitch_and_save_partial_audio(temp_dir_path, original_output_filename):
    # Method for when voice generation fails - finds existing chunks and stitches them into a partial audio file, if requested
    print("\n--- Attempting to save partial audio ---")
    chunk_files = sorted(glob.glob(os.path.join(temp_dir_path, "chunk_*.mp3")))
    
    if not chunk_files:
        print("No completed chunks found to save.")
        return

    num_chunks_saved = len(chunk_files)
    print(f"Found {num_chunks_saved} completed chunks.")
    
    # Create a new name for the partial file to avoid confusion
    base, ext = os.path.splitext(original_output_filename)
    partial_filename = f"{base}_partial_to_chunk_{num_chunks_saved}{ext}"
    
    print(f"Combining chunks into '{partial_filename}'...")
    with open(partial_filename, "wb") as out_file:
        for chunk_file in chunk_files:
            with open(chunk_file, "rb") as in_chunk:
                out_file.write(in_chunk.read())
    
    print(f"Partial audiobook saved successfully as '{partial_filename}'")