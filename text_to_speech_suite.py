import os
from prompt_toolkit import prompt
from prompt_toolkit.completion import PathCompleter

from config import * 
from utility_functions import get_unique_filename, open_file_for_editing, calculate_tts_cost, load_custom_fixes_from_file
from pdf_core_text_extractor import extract_and_clean_pdf_text
from google_ai_tts_converter import text_to_speech_converter
from pdf_AI_text_extractor import extract_text_with_gemini
from epub_creator import create_epub_from_text

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

    handle_epub_generation(clean_text, pdf_path)

    generate_audio_from_text(clean_text, pdf_path)

def extract_pdf_only_workflow():
    # Ask for PDF
    path_completer = PathCompleter()
    pdf_path = prompt(">>> Enter the path to your PDF file: ", completer=path_completer)
    if not os.path.exists(pdf_path):
        print(f"!!! Error: File not found at {pdf_path}")
        return
    
    start_input = input(">>> Start from Page number (default 1): ").strip()
    if start_input.isdigit() and int(start_input) > 0:
        start_page_index = int(start_input) - 1
    else:
        start_page_index = 0

    end_input = input(">>> End at Page number (default: End of file): ").strip()
    end_page_index = None
    if end_input.isdigit() and int(end_input) > 0:
        end_page_index = int(end_input)

    fixes_path = prompt(">>> Path to custom replacements file (optional): ", completer=path_completer).strip()
    user_fixes = {}
    if fixes_path:
        # If user typed something, try to load it
        # If user just hit Enter, skip
        user_fixes = load_custom_fixes_from_file(fixes_path)

    # Extract
    # clean_text = extract_and_clean_pdf_text(pdf_path)
    clean_text = extract_and_clean_pdf_text(pdf_path, 
                                            start_page_index, 
                                            end_page_index,
                                            custom_replacements=user_fixes)
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

def handle_epub_generation(text_content, source_path):
    print("\n---------------------------------------------------------------")
    print("                      EPUB EXPORT")
    print("  Creates a .epub book optimized for Voice Dream / Apple Books.")
    print("  Includes automatic Table of Contents based on document headings.")
    print("---------------------------------------------------------------")
    
    do_epub = input(">>> Generate EPUB file? (y/N): ").lower()
    
    if do_epub == 'y':
        # Suggest a filename
        base_name = os.path.splitext(os.path.basename(source_path))[0]
        
        output_folder = EPUB_OUTPUT_FOLDER
        os.makedirs(output_folder, exist_ok=True)
        
        epub_path = os.path.join(output_folder, f"{base_name}.epub")
        epub_path = get_unique_filename(epub_path)
        
        create_epub_from_text(text_content, epub_path, title=base_name)

def process_txt_to_epub_workflow():
    path_completer = PathCompleter()
    print("\n######################### Text to EPUB Converter ##############################")
    print("#                                                                             #")
    print("#  Converts a raw .txt file into a structured EPUB audiobook.                 #")
    print("#  - Auto-detects chapters based on headings.                                 #")
    print("#  - Creates a Table of Contents for easy navigation.                         #")
    print("#                                                                             #")
    print("###############################################################################\n")
    
    txt_path = prompt(">>> Enter the path to your .txt file: ", completer=path_completer)

    if not os.path.exists(txt_path):
        print(f"\n!!! Error: File does not exist at '{txt_path}' !!!")
        return

    try:
        print(f"Reading text from '{txt_path}'...")
        with open(txt_path, 'r', encoding='utf-8') as f:
            text_content = f.read()
        
        # Ensure output directory exists
        os.makedirs(EPUB_OUTPUT_FOLDER, exist_ok=True)
        
        # 1. Determine base name from source file
        base_name = os.path.splitext(os.path.basename(txt_path))[0]
        
        # 2. Construct default full path in EPUB folder
        default_filename = f"{base_name}.epub"
        
        # 3. Check for uniqueness, show user likely actual name
        suggestion_path = os.path.join(EPUB_OUTPUT_FOLDER, default_filename)
        unique_suggestion_path = get_unique_filename(suggestion_path)
        unique_suggestion_name = os.path.basename(unique_suggestion_path)
        
        # 4. Ask for custom name or accept default
        user_input = input(f">>> Enter output filename (default: {unique_suggestion_name}): ").strip()
        
        if not user_input:
            final_output_path = unique_suggestion_path
        else:
            # If user typed a name, make sure it ends in .epub
            if not user_input.lower().endswith('.epub'):
                user_input += ".epub"
            
            # Combine user input with enforced folder
            custom_path = os.path.join(EPUB_OUTPUT_FOLDER, user_input)
            # Ensure custom path is also unique
            final_output_path = get_unique_filename(custom_path)

        # 5. Generate
        create_epub_from_text(text_content, final_output_path, title=base_name)
        
    except Exception as e:
        print(f"!!! Error processing file: {e} !!!")

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
        print("4: Generate EPUB from an existing .txt file")
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
        elif choice == '4':
            process_txt_to_epub_workflow()
            break
        elif choice == 'q':
            break
        else:
            print("\n!!! Invalid choice, please try again. !!!")

    print("\nScript finished.")

if __name__ == "__main__":
    main()
