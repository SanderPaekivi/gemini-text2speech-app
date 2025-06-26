import time
from tqdm import tqdm
from google.cloud import texttospeech
from google.api_core import exceptions as google_exceptions

def text_to_speech_converter(text, output_filename, TTS_CHUNK_SIZE=4500, MAX_RETRIES=5, INITIAL_BACKOFF=2):
    # Chunks text to max chunk size (per specs, see documentation) and uses Google Cloud TTS to generate an audio file (includes retry mechanism for server side errors)
    print("\n --- Synthesizing Audio --- ")
    if not text:
        print("No text to synthesize. Aborting.")
        return
        
    try:
        tts_client = texttospeech.TextToSpeechClient()
    except Exception as e:
        print(f"\n!!! Google Cloud Authentication Error: Could not initialize client: {e} !!!")
        return

    text_chunks = [text[i:i + TTS_CHUNK_SIZE] for i in range(0, len(text), TTS_CHUNK_SIZE)]
    print(f"Text split into {len(text_chunks)} chunks for audio synthesis.")
    
    audio_segments = []
    # Using enumerate to track the chunk number for logging
    for index_of_chunk, chunk in enumerate(tqdm(text_chunks, desc="Synthesizing audio...")):
        retries = 0
        backoff_time = INITIAL_BACKOFF
        while retries < MAX_RETRIES:
            try:
                synthesis_input = texttospeech.SynthesisInput(text=chunk)
                voice = texttospeech.VoiceSelectionParams(language_code="en-US", name="en-US-Chirp3-HD-Aoede")
                audio_config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.MP3)
                
                if retries == 0:
                    print(f"\n[Chunk {index_of_chunk+1}/{len(text_chunks)}] Requesting voice: {voice.name}...")
                
                response = tts_client.synthesize_speech(input=synthesis_input, voice=voice, audio_config=audio_config)
                audio_segments.append(response.audio_content)
                break

            except google_exceptions.ServiceUnavailable as e:
                print(f"\n ??? Warning: Server error on chunk {index_of_chunk+1}. Retrying in {backoff_time}s... (Attempt {retries + 2}/{MAX_RETRIES}) ???")
                time.sleep(backoff_time)
                retries += 1
                backoff_time *= 2
            
            except Exception as e:
                print(f"\n!!! An unrecoverable error occurred on chunk {index_of_chunk+1}: {e} !!!")
                return

        if len(audio_segments) != len(text_chunks):
            print(f"\n!!! Failed to process all chunks after multiple retries. Aborting audio generation !!!")
            return

    print(f"\nCombining audio segments into '{output_filename}'...")
    with open(output_filename, "wb") as out:
        for segment in audio_segments:
            out.write(segment)
            
    print("\n Combining generated audio complete.")
    print(f"Audiobook saved as '{output_filename}'")