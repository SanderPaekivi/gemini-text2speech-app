import os
from prompt_toolkit import prompt
from prompt_toolkit.completion import PathCompleter

from config import * 
from utility_functions import get_unique_filename, open_file_for_editing, calculate_tts_cost
from pdf_core_text_extractor import extract_and_clean_pdf_text
from google_ai_tts_converter import text_to_speech_converter
from pdf_AI_text_extractor import extract_text_with_gemini
from text_postprocessing import clean_extracted_text
from gemini_ai_text_postprocessor import fix_text_with_ai

##############################################################################################################################
##############################################################################################################################
##############################################################################################################################

def process_ai_extraction_workflow():
    path_completer = PathCompleter()
    print("\n AI Text Extraction  (Gemini) ---")
    pdf_path = prompt(">>> Enter path to PDF: ", completer=path_completer)

    if not os.path.exists(pdf_path):
        print("!!! File not found.")
        return

    start_page_input = input(">>> Start from Page number (default 1): ").strip()
    if start_page_input.isdigit() and int(start_page_input) > 0:
        start_page_index = int(start_page_input) - 1
    else:
        start_page_index = 0
    
    end_input = input(">>> End at Page number (default: End of file): ").strip()
    end_page_index = None # None means to end
    
    if end_input.isdigit() and int(end_input) > 0:
        end_page_index = int(end_input)
    
    clean_text = extract_text_with_gemini(pdf_path, start_page_index, end_page_index)
    # clean_text = extract_text_with_gemini(pdf_path)

    if clean_text:
        os.makedirs(TEXT_OUTPUT_FOLDER, exist_ok=True)
        base_name = os.path.splitext(os.path.basename(pdf_path))[0]
        output_path = get_unique_filename(os.path.join(TEXT_OUTPUT_FOLDER, f"{base_name}_AI_extracted.txt"))

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(clean_text)

        print(f"\nSUCCESS: AI Text saved to: '{output_path}'")
        if input(">>> Open for review? (y/N): ").lower() == 'y':
            open_file_for_editing(output_path)

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

def extract_pdf_only_workflow():
    # Ask for PDF
    path_completer = PathCompleter()
    pdf_path = prompt(">>> Enter the path to your PDF file: ", completer=path_completer)
    if not os.path.exists(pdf_path):
        print(f"!!! Error: File not found at {pdf_path}")
        return

    # Extract
    clean_text = extract_and_clean_pdf_text(pdf_path)
    if not clean_text: 
        return

    # Save txt
    os.makedirs(TEXT_OUTPUT_FOLDER, exist_ok=True)
    base_name = os.path.splitext(os.path.basename(pdf_path))[0]
    text_filepath = get_unique_filename(os.path.join(TEXT_OUTPUT_FOLDER, f"{base_name}_textract.txt"))
    
    with open(text_filepath, 'w', encoding='utf-8') as f:
        f.write(clean_text)
    
    print(f"\nSUCCESS: Text saved to '{text_filepath}'")
    
    # Option to open for edit
    if input(">>> Open file for review/editing now? (y/N): ").lower() == 'y':
        open_file_for_editing(text_filepath)

def process_txt_workflow():
    # Workflow for generating audio from a text (.txt) file
    path_completer = PathCompleter()
    print("\n######################### How to Navigate #####################################")
    print("#                                                                             #")
    print("# - Press TAB to see available files and folders.                             #")
    print("# - Use '/' to select a directory and see internal content.                   #")
    print("# - Use '../' to go up to the parent directory.                               #")
    print("# - For WSL: your C: drive is at '/mnt/c/'.                                   #")
    print("#                                                                             #")
    print("###############################################################################\n")
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
    char_count = len(text_content)
    estimated_cost = calculate_tts_cost(char_count, PRICE_PER_MILLION_CHARS_HD)

    print("\n###############################################################")
    print("#                        Cost Estimation")
    print(f"# Total characters in given text to synthesize: {char_count}")
    print(f"# Estimated cost: ${estimated_cost:.4f}")
    print("#")
    print("#                      IMPORTANT")
    print(f"# Your Google Cloud account includes a free tier of")
    print(f"# {FREE_TIER_LIMIT:,} characters per month for HD voices.")
    print("# This estimate does NOT account for your remaining free tier!")
    print("# To check your current usage, visit your")
    print("# Google Cloud Console Billing page.")
    print("###############################################################")

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

        text_to_speech_converter(text_content, output_filename, PRICE_PER_MILLION_CHARS_HD, TTS_CHUNK_SIZE, MAX_RETRIES, INITIAL_BACKOFF)
    else:
        print("Skipping audio generation.")

##############################################################################################################################
################################################### Main Execution ###########################################################
##############################################################################################################################

def main():
    print("#######################################\n##### PDF to audio conversion CLI #####\n#######################################")
    path_completer = PathCompleter()
    while True:
        print("\nPlease choose an option:")
        print("1: Process a new PDF file")
        print("2: AI Smart Extraction from PDF (Gemini)")
        print("3: Generate audio from an existing .txt file")
        # print("4: Apply Regex Cleanup to a text file") #NOTE: Not necessary for now, kind of trash... 
        # print("5: Apply AI Repair to txt (Gemini)")
        print("Q: Quit")
        
        choice = input(">>> Your choice: ").lower()
        
        if choice == '1':
            extract_pdf_only_workflow()
            break
        elif choice == '2':
            process_ai_extraction_workflow()
            break
        elif choice == '3':
            process_txt_workflow()
            break
        # elif choice == '4':
        #     txt_path = prompt(">>> Enter path to .txt file: ", completer=path_completer)
        #     clean_extracted_text(txt_path)
        # elif choice == '5':
        #     txt_path = prompt(">>> Enter path to .txt file: ", completer=path_completer)
        #     fix_text_with_ai(txt_path)
        elif choice == 'q':
            break
        else:
            print("\n!!! Invalid choice, please try again. !!!")

    print("\nScript finished.")

if __name__ == "__main__":
    main()
