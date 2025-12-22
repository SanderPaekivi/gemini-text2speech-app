import os
import time
import shutil
import re
import pymupdf
from google import genai
from google.genai import types

try:
    from config import CREDENTIALS_FILE
except ImportError:
    pass

def extract_text_with_gemini(pdf_path):
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("!!! Error: GOOGLE_API_KEY not found. !!!")
        return None

    client = genai.Client(api_key=api_key)
    
    # Using an overlap so sentences arent cut off
    CHUNK_SIZE = 20      # Pages to process per API call
    OVERLAP = 1          # Pages to overlap for context
    
    filename_base = os.path.splitext(os.path.basename(pdf_path))[0]
    
    # dir of outputs from batches
    batch_output_dir = os.path.join("extracted_batches", filename_base)
    if os.path.exists(batch_output_dir):
        shutil.rmtree(batch_output_dir)
    os.makedirs(batch_output_dir, exist_ok=True)
    
    # dir of PDF splits for batches
    temp_split_dir = "temp_pdf_splits"
    if os.path.exists(temp_split_dir):
        shutil.rmtree(temp_split_dir)
    os.makedirs(temp_split_dir, exist_ok=True)

    print(f"\n--- Processing '{filename_base}' ---")
    print(f"Intermediate batches will be saved to: {batch_output_dir}/")
    
    doc = pymupdf.open(pdf_path)
    total_pages = len(doc)
    print(f"Total Pages: {total_pages}")
    
    full_book_text = []

    try:
        # sliding window loop, step forward by (CHUNK_SIZE - OVERLAP) to create the overlap
        step_size = CHUNK_SIZE - OVERLAP
        # to not get stuck in a loop if step_size is <= 0
        if step_size < 1: step_size = 1

        batch_num = 1
        
        for start_page in range(0, total_pages, step_size):
            end_page = min(start_page + CHUNK_SIZE, total_pages)
            
            # Stop if past the end
            if start_page >= total_pages:
                break

            # create chunk PDF
            chunk_filename = os.path.join(temp_split_dir, f"batch_{batch_num:03d}.pdf")
            new_doc = pymupdf.open()
            new_doc.insert_pdf(doc, from_page=start_page, to_page=end_page - 1)
            new_doc.save(chunk_filename)
            new_doc.close()

            print(f"\nBatch {batch_num} (Pages {start_page+1}-{end_page})...")
            
            # determine if this is the first batch (doesnt have overlap context)
            has_overlap_context = (start_page > 0)
            
            # extract
            batch_text = _process_single_chunk(client, chunk_filename, has_overlap_context)
            
            if batch_text:
                batch_save_path = os.path.join(batch_output_dir, f"batch_{batch_num:03d}.txt")
                with open(batch_save_path, "w", encoding="utf-8") as f:
                    f.write(batch_text)
                
                full_book_text.append(batch_text)
                print(f"  -> Saved to {batch_save_path}")
            else:
                print(f"!!! Warning: Batch {batch_num} returned no text.")

            batch_num += 1
            # being nice to the API
            time.sleep(2)

    finally:
        doc.close()
        # Clean up the split PDFs, but keep text batches
        if os.path.exists(temp_split_dir):
            shutil.rmtree(temp_split_dir)

    print("\n--- Book Extraction Complete ---")
    
    # merge all batches
    final_text = "\n".join(full_book_text)
    
    # final cleanup, can do regex
    # this now catches "word- \n part" that might have survived
    final_text = re.sub(r'([a-zA-Z]+)-\s*\n\s*', r'\1', final_text)
    
    return final_text

def _process_single_chunk(client, chunk_path, has_context_page):
    # Helper to process one chunk
    try:
        sample_file = client.files.upload(file=chunk_path)
        
        while sample_file.state.name == "PROCESSING":
            time.sleep(1)
            sample_file = client.files.get(name=sample_file.name)
            
        if sample_file.state.name == "FAILED":
            return None

        # prompt based on position
        context_instruction = ""
        if has_context_page:
            context_instruction = "IMPORTANT: The first page of this PDF is provided for CONTEXT ONLY (it was the last page of the previous batch). DO NOT extract text from the first page. Start extraction from the second page. Ensure the sentence bridging the first and second page is completed naturally."

        prompt = f"""
        You are an expert audiobook editor. Convert this PDF chunk into clean text.
        
        {context_instruction}
        
        STRICT CLEANING RULES:
        1. REMOVE RUNNING HEADERS: Delete repeated author names or chapter titles at page margins.
        2. REMOVE META-DATA: No page numbers.
        3. CONTENT: Exclude Acknowledgments, Tables, Figures, and Citations.
        4. FLOW: Fix hyphenated words splits.
        5. OUTPUT: Plain text only. No markdown.
        """

        response_stream = client.models.generate_content_stream(
            model='gemini-2.0-flash', 
            contents=[sample_file, prompt],
            config=types.GenerateContentConfig(temperature=0.1)
        )
        
        chunk_text_parts = []
        print("  Receiving: ", end="", flush=True)
        
        for chunk in response_stream:
            print(".", end="", flush=True)
            if chunk.text:
                chunk_text_parts.append(chunk.text)
        
        try:
            client.files.delete(name=sample_file.name)
        except:
            pass
            
        return "".join(chunk_text_parts)

    except Exception as e:
        print(f"\nError in batch: {e}")
        return None