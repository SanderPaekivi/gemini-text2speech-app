import os
import time
import glob
import shutil
from tqdm import tqdm
from google.cloud import texttospeech
from google.api_core import exceptions as google_exceptions

from utility_functions import stitch_and_save_partial_audio

def text_to_speech_converter(text, output_filename, TTS_CHUNK_SIZE=4500, MAX_RETRIES=5, INITIAL_BACKOFF=2):
    # Chunks text to max chunk size (per specs, see documentation) and uses Google Cloud TTS to generate an audio file (includes retry mechanism for server side errors)
    print("\n --- Synthesizing Audio --- ")
    if not text:
        print("No text to synthesize. Aborting.")
        return
    
    temp_dir_name = os.path.splitext(os.path.basename(output_filename))[0] + "_temp_chunks"
    temp_dir_path = os.path.join(os.path.dirname(output_filename), temp_dir_name)
    os.makedirs(temp_dir_path, exist_ok=True)
    print(f"Chunks will be temporarily stored in: '{temp_dir_path}'")
        
    try:
        tts_client = texttospeech.TextToSpeechClient()
    except Exception as e:
        print(f"\n!!! Google Cloud Authentication Error: Could not initialize client: {e} !!!")
        return

    text_chunks = [text[i:i + TTS_CHUNK_SIZE] for i in range(0, len(text), TTS_CHUNK_SIZE)]
    print(f"Text split into {len(text_chunks)} chunks for audio synthesis.")
    
    for index_of_chunk, chunk in enumerate(tqdm(text_chunks, desc="Synthesizing audio...")):
        # Define the path for this specific chunk audio file
        chunk_filename = os.path.join(temp_dir_path, f"chunk_{index_of_chunk:04d}.mp3")
        
        # If the chunk file already exists, skip the API call
        if os.path.exists(chunk_filename):
            tqdm.write(f"\n[Chunk {index_of_chunk+1}/{len(text_chunks)}] Found existing chunk file. Skipping API call.")
            continue
            
        retries = 0
        backoff_time = INITIAL_BACKOFF
        
        while retries < MAX_RETRIES:
            try:
                synthesis_input = texttospeech.SynthesisInput(text=chunk)
                voice = texttospeech.VoiceSelectionParams(language_code="en-US", name="en-US-Chirp3-HD-Aoede")
                audio_config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.MP3)
                
                if retries == 0:
                    tqdm.write(f"\n[Chunk {index_of_chunk+1}/{len(text_chunks)}] Requesting voice: {voice.name}...")
                
                response = tts_client.synthesize_speech(
                    input=synthesis_input, 
                    voice=voice, 
                    audio_config=audio_config,
                    timeout=120.0
                )
                
                # Save the successful chunk immediately
                with open(chunk_filename, "wb") as out:
                    out.write(response.audio_content)
                
                break # Success, exit the retry loop

            except (google_exceptions.ServiceUnavailable, google_exceptions.DeadlineExceeded) as e:
                error_type = "Server error" if isinstance(e, google_exceptions.ServiceUnavailable) else "Timeout (Deadline Exceeded)"
                tqdm.write(f"\n ??? Warning: {error_type} on chunk {index_of_chunk+1}. Retrying in {backoff_time}s... (Attempt {retries + 2}/{MAX_RETRIES}) ???")
                time.sleep(backoff_time)
                retries += 1
                backoff_time *= 2
            
            except Exception as e:
                print(f"\n!!! An unrecoverable error occurred on chunk {index_of_chunk+1}: {e} !!!")
                save_partial = input("\n>>> Would you like to save the audio processed so far? (y/N): ").lower()
                if save_partial == 'y':
                    stitch_and_save_partial_audio(temp_dir_path, output_filename)
                print("Aborting synthesis. Run the script again with the same output filename to resume.")
                return

        # Check if this specific chunk failed after all retries
        if not os.path.exists(chunk_filename):
            print(f"\n!!! Failed to process chunk {index_of_chunk+1} after multiple retries. Aborting. !!!")
            save_partial = input("\n>>> Would you like to save the audio processed so far? (y/N): ").lower()
            if save_partial == 'y':
                stitch_and_save_partial_audio(temp_dir_path, output_filename)
            print("Run the script again with the same output filename to resume.")
            return

    # Combine chunks
    print(f"\nAll chunks processed successfully. Combining into '{output_filename}'...")
    
    # Find all chunk files in the temporary directory and sort them
    chunk_files = sorted(glob.glob(os.path.join(temp_dir_path, "chunk_*.mp3")))

    with open(output_filename, "wb") as out_file:
        for chunk_file in chunk_files:
            with open(chunk_file, "rb") as in_chunk:
                out_file.write(in_chunk.read())
    
    print("\nCombining generated audio complete.")
    print(f"Audiobook saved as '{output_filename}'")

    # Cleanup of temporary directory
    try:
        print(f"Cleaning up temporary directory: '{temp_dir_path}'")
        shutil.rmtree(temp_dir_path)
        print("Cleanup complete.")
    except Exception as e:
        print(f"\n!!! Warning: Could not remove temporary directory. Error: {e} !!!")
        print("You can manually delete it if desired.")