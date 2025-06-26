import os
import time
from prompt_toolkit import prompt
from prompt_toolkit.completion import PathCompleter

from utility_functions import get_unique_filename, open_file_for_editing
from pdf_core_text_extractor import extract_and_clean_pdf_text
from google_ai_tts_converter import text_to_speech_converter

##############################################################################################################################
##################################################### Configuration ##########################################################
##############################################################################################################################

# Set up authentication for the Google Cloud Text-to-Speech service
CREDENTIALS_FILE = "google-credentials.json"
if os.path.exists(CREDENTIALS_FILE):
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = CREDENTIALS_FILE
else:
    print(f"Authentication Error: '{CREDENTIALS_FILE}' not found.")
    print("Please download your service account key from Google Cloud and save it in the project folder. It is gitignored!")
    exit()

# Maximum characters a single API request to Google TTS can be (TODO: Check validity and options)
TTS_CHUNK_SIZE = 4500
# For retry-mechanism, had some server-side errors before... (TODO: Perhaps remove)
MAX_RETRIES = 5
INITIAL_BACKOFF = 2  # unit in seconds

TEXT_OUTPUT_FOLDER = "extracted texts" #NOTE: Changing these folder names will make them visible to git, so be careful!
AUDIO_OUTPUT_FOLDER = "generated audio"

##############################################################################################################################
##############################################################################################################################
##############################################################################################################################

def process_pdf_workflow():
    # Workflow for processing a PDF file
    path_completer = PathCompleter()
    print("\n################################# How to Navigate ###########################")
    print("#                                                                             #")
    print("# - Press TAB to see available files and folders.                             #")
    print("# - Use '../' to go up to the parent directory.                               #")
    print("# - For WSL: your C: drive is at '/mnt/c/'.                                   #")
    print("#                                                                             #")
    print("###############################################################################\n")
    pdf_path = prompt(">>> Enter the path to your PDF file: ", completer=path_completer)

    if not os.path.exists(pdf_path):
        print(f"\n!!! Error: File does not exist at '{pdf_path}' !!!")
        return

    clean_text = extract_and_clean_pdf_text(pdf_path)
    if not clean_text:
        return

    save_text = input("\n>>> Do you want to save the cleaned text to a .txt file for review? (y/N): ").lower()
    if save_text == 'y':
        os.makedirs(TEXT_OUTPUT_FOLDER, exist_ok=True)
        base_name = os.path.splitext(os.path.basename(pdf_path))[0]
        text_filename_suggestion = os.path.join(TEXT_OUTPUT_FOLDER, f"{base_name}_textract.txt")
        text_filepath = get_unique_filename(text_filename_suggestion)
    
        try:
            with open(text_filepath, 'w', encoding='utf-8') as f:
                f.write(clean_text)
            print(f"Cleaned text saved to '{text_filepath}'")

            edit_text = input(">>> Do you want to open this file for manual editing? (y/N): ").lower()
            if edit_text == 'y':
                open_file_for_editing(text_filepath)
                input("\n>>> After you have finished editing and saved the file, press Enter here to continue...")
                
                print("Re-reading edited text file...")
                with open(text_filepath, 'r', encoding='utf-8') as f:
                    clean_text = f.read()
                print("Text updated with manual edits.")

        except Exception as e:
            print(f"!!! Error during file handling or editing: {e} !!!")

    generate_audio_from_text(clean_text, pdf_path)

def process_txt_workflow():
    # Workflow for generating audio from a text (.txt) file
    path_completer = PathCompleter()
    txt_path = prompt(">>> Enter the path to your .txt file: ", completer=path_completer)

    if not os.path.exists(txt_path):
        print(f"\n!!! Error: File does not exist at '{txt_path}' !!!")
        return

    try:
        print(f"Reading text from '{txt_path}'...")
        with open(txt_path, 'r', encoding='utf-8') as f:
            text_to_synthesize = f.read()
        print("Text successfully loaded.")
        generate_audio_from_text(text_to_synthesize, txt_path)
    except Exception as e:
        print(f"!!! Error reading text file: {e} !!!")

def generate_audio_from_text(text_content, source_path):
    # Method for prompting user and starting audio synthesis
    create_audio = input("\n>>> Do you want to proceed with generating the audio file? (Y/n): ").lower()
    if not create_audio or create_audio == 'y':
        os.makedirs(AUDIO_OUTPUT_FOLDER, exist_ok=True)
        base_name = os.path.splitext(os.path.basename(source_path))[0]
        default_output_suggestion = os.path.join(AUDIO_OUTPUT_FOLDER, f"{base_name}.mp3")
        
        unique_default_name = get_unique_filename(default_output_suggestion)
        
        output_filename = input(f">>> Enter the desired output MP3 path (default: {unique_default_name}): ")
        if not output_filename:
            output_filename = unique_default_name

        output_filename = get_unique_filename(output_filename)

        text_to_speech_converter(text_content, output_filename, TTS_CHUNK_SIZE, MAX_RETRIES, INITIAL_BACKOFF)
    else:
        print("Skipping audio generation.")

##############################################################################################################################
################################################### Main Execution ###########################################################
##############################################################################################################################

def main():
    print("#######################################\n##### PDF to audio conversion CLI #####\n#######################################")
    
    while True:
        print("\nPlease choose an option:")
        print("1: Process a new PDF file")
        print("2: Generate audio from an existing .txt file")
        print("Q: Quit")
        
        choice = input(">>> Your choice: ").lower()
        
        if choice == '1':
            process_pdf_workflow()
            break
        elif choice == '2':
            process_txt_workflow()
            break
        elif choice == 'q':
            break
        else:
            print("\n!!! Invalid choice, please try again. !!!")

    print("\nScript finished.")

if __name__ == "__main__":
    main()
