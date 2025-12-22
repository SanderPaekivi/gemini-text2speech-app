import os
import time
import shutil
from google import genai
from google.genai import types

GEMINI_MODEL = 'gemini-2.5-pro'

try:
    from config import GEMINI_API_KEY
except ImportError:
    pass

def fix_text_with_ai(input_path):
    # Setup API
    api_key = GEMINI_API_KEY
    if not api_key:
        print("!!! Error: API Key not found. !!!")
        return

    if not os.path.exists(input_path):
        print(f"File not found: {input_path}")
        return

    # checking file size in case its sus large, over 50MB suggests extraction loop error
    file_size_mb = os.path.getsize(input_path) / (1024 * 1024)
    if file_size_mb > 50:
        print(f"!!! WARNING: Input file is {file_size_mb:.2f} MB. This is very large for a text file.")
        print("!!! Might want to check if the extraction step created an infinite loop.")
        if input(">>> Continue anyway? (y/N) ").lower() != 'y':
            return

    client = genai.Client(api_key=api_key)
    
    base_name = os.path.splitext(os.path.basename(input_path))[0]
    final_output_path = f"{base_name}_AI_polished.txt"
    
    # batch folder for debugging (keeping for now just incase)
    batch_dir = os.path.join("polished_batches", base_name)
    if os.path.exists(batch_dir): shutil.rmtree(batch_dir)
    os.makedirs(batch_dir, exist_ok=True)

    print(f"\n Polishing extracted text, streaming: '{base_name}'. ")
    print(f"Target Model: {GEMINI_MODEL}")
    
    # CONFIG
    CHUNK_SIZE = 15000 
    OVERLAP = 500

    # open both files at once, read a chunk, fix it, write it, and forget it
    # 1. creating/wiping output file first
    with open(final_output_path, 'w', encoding='utf-8') as f:
        pass 

    with open(input_path, 'r', encoding='utf-8') as f_in:
        batch_count = 0
        
        while True:
            # marking current position to back up for overlap
            current_pos = f_in.tell()
            
            # reading one chunk into RAM
            chunk_text = f_in.read(CHUNK_SIZE)
            
            # end of file check
            if not chunk_text:
                break
                
            batch_count += 1
            print(f"\nBatch {batch_count} ({len(chunk_text)} chars)...", end=" ", flush=True)

            is_first = (batch_count == 1)
            
            # processing
            fixed_chunk = _clean_chunk_stream(client, chunk_text, is_first)
            
            # fallback, should do more here...
            if not fixed_chunk:
                print(" -> Failed. Copying original.")
                fixed_chunk = chunk_text
            
            # writing immediately
            with open(final_output_path, 'a', encoding='utf-8') as f_out:
                f_out.write(fixed_chunk + "\n")
                
            # saving debug batch
            with open(os.path.join(batch_dir, f"batch_{batch_count:03d}.txt"), 'w', encoding='utf-8') as f_debug:
                f_debug.write(fixed_chunk)
            
            print(f" -> Appended to output.")
            
            # when reading a full chunk, back up the pointer
            if len(chunk_text) == CHUNK_SIZE:
                f_in.seek(current_pos + CHUNK_SIZE - OVERLAP)
            else:
                # when reading less than CHUNK_SIZE, likely reached the end
                break
                
            # being nice to the API
            time.sleep(4)

    print(f"\n Polishing complete.")
    print(f"File saved to: {final_output_path}")

def _clean_chunk_stream(client, text, is_first_chunk):
    # Streams response from Gemini
    context_note = ""
    if not is_first_chunk:
        context_note = "NOTE: The first few lines might overlap with the previous batch. If they are incomplete sentence fragments, merge them naturally."

    prompt = f"""
    You are a professional audiobook editor. Your goal is to repair the following text extracted from a PDF.
    
    {context_note}
    
    INSTRUCTIONS:
    1. IDENTIFY INTRUSIONS: The text contains random "artifacts" inserted by the PDF layout. These include page numbers (e.g., '104', 'IX'), running headers (author names, book titles), and footers.
    2. SURGICAL REPAIR: These artifacts often appear inside sentences or even split words in half. You must detect them based on context (they disrupt the grammar) and delete them.
    3. MERGE SPLIT WORDS: If a word is split by an artifact or a newline (e.g., "unwaver- [Header 12] ing" or "gen eral"), delete the artifact and merge the word ("unwavering", "general").
    4. PRESERVE NARRATIVE: Do not summarize. Keep the original content exactly as is, only removing the technical flaws.
    4.1 JUMBLED CONTENT: If text appears suddenly nonsensical (tables, graph labels), remove it.
    5. FORMATTING: Output clean text with standard paragraph spacing.
    
    INPUT TEXT:
    {text}
    """

    try:
        response_stream = client.models.generate_content_stream(
            model=GEMINI_MODEL, 
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.1)
        )
        
        accumulated_text = []
        for chunk in response_stream:
            if chunk.text:
                print(".", end="", flush=True)
                accumulated_text.append(chunk.text)
                
        return "".join(accumulated_text)

    except Exception as e:
        print(f"\n!!! AI Error: {e}")
        return None

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        fix_text_with_ai(sys.argv[1])
    else:
        # Drag and drop should work too
        path = input(">>> Enter path to .txt file: ").strip().strip('"').strip("'")
        fix_text_with_ai(path)