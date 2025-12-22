import os
import time
import shutil
import re
import pymupdf
from google import genai
from google.genai import types

from utility_functions import smart_stitch

try:
    from config import GEMINI_API_KEY
except ImportError:
    pass

ai_model = 'gemini-2.5-pro' #'gemini-2.0-flash'

def extract_text_with_gemini(pdf_path, start_page_index=0):
    api_key = GEMINI_API_KEY
    if not api_key:
        print("!!! Error: GOOGLE_API_KEY not found. !!!")
        return None

    client = genai.Client(api_key=api_key)
    
    # Using an overlap so sentences arent cut off
    if ai_model == 'gemini-2.5-pro':
        CHUNK_SIZE = 50      # Pages to process per API call
        OVERLAP = 1          # Pages to overlap for context
    else:
        CHUNK_SIZE = 20      # less for lower models... NOTE: should implement model selection and vars based on that. 
        OVERLAP = 1
    
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

    print(f"\n Processing '{filename_base}'. ")
    print(f"Intermediate batches will be saved to: {batch_output_dir}/")
    
    doc = pymupdf.open(pdf_path)
    total_pages = len(doc)
    print(f"Total Pages: {total_pages}")
    
    full_book_text = []
    previous_anchor_text = None

    try:
        # sliding window loop, step forward by (CHUNK_SIZE - OVERLAP) to create the overlap
        step_size = CHUNK_SIZE - OVERLAP
        # to not get stuck in a loop if step_size is <= 0
        if step_size < 1: step_size = 1

        batch_num = 1
        
        for start_page in range(start_page_index, total_pages, step_size):
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

            batch_text = _process_single_chunk_anchor(client, chunk_filename, previous_anchor_text)
            
            # # determine if this is the first batch (doesnt have overlap context)
            # has_overlap_context = (start_page > 0)
            
            # # extract
            # batch_text = _process_single_chunk(client, chunk_filename, has_overlap_context)
            
            # if batch_text:
            #     batch_save_path = os.path.join(batch_output_dir, f"batch_{batch_num:03d}.txt")
            #     with open(batch_save_path, "w", encoding="utf-8") as f:
            #         f.write(batch_text)
                
            #     # full_book_text.append(batch_text)
            #     # print(f"  -> Saved to {batch_save_path}")
            #     print(f"  -> Stitching batch {batch_num}...", end=" ")
            #     full_book_text = smart_stitch(full_book_text, batch_text)
            # else:
            #     print(f"!!! Warning: Batch {batch_num} returned no text.")

            # batch_num += 1

            if batch_text:
                batch_save_path = os.path.join(batch_output_dir, f"batch_{batch_num:03d}.txt")
                with open(batch_save_path, "w", encoding="utf-8") as f:
                    f.write(batch_text)
                
                # Append directly, no stitching needed if AI obeys the anchor...
                full_book_text.append(batch_text)
                print(f"  -> Extracted {len(batch_text)} chars.")
                
                # New anchor method
                # Grab the last ~300 characters (approx 2-3 sentences)
                # strip whitespace to make matching easier
                clean_batch = batch_text.strip()
                if len(clean_batch) > 300:
                    previous_anchor_text = clean_batch[-300:]
                else:
                    previous_anchor_text = clean_batch # fallback for tiny batches
            else:
                print(f"!!! Warning: Batch {batch_num} returned no text.")
                # Keep the old anchor if this batch failed, or set to None?

            batch_num += 1
            # if batch_num == 4:
            #     break
            # being nice to the API
            time.sleep(2)

    finally:
        doc.close()
        # Clean up the split PDFs, but keep text batches
        if os.path.exists(temp_split_dir):
            shutil.rmtree(temp_split_dir)

    print("\n Extraction Complete.")
    
    # merge all batches
    # final_text = "\n".join(full_book_text)
    # final_text = full_book_text
    final_text = " ".join(full_book_text)
    
    # final cleanup, can do regex
    # this now catches "word- \n part" that might have survived
    final_text = re.sub(r'([a-zA-Z]+)-\s*\n\s*', r'\1', final_text)
    final_text = re.sub(r'\s+', ' ', final_text)
    
    return final_text

def _process_single_chunk_anchor(client, chunk_path, anchor_text):
    try:
        sample_file = client.files.upload(file=chunk_path)
        while sample_file.state.name == "PROCESSING":
            time.sleep(1)
            sample_file = client.files.get(name=sample_file.name)
        if sample_file.state.name == "FAILED":
            return None

        # Dynamic prompt with anchor info
        
        instructions = ""
        
        if anchor_text:
            instructions = f"""
            *** IMPORTANT: CONTINUATION INSTRUCTION ***
            The previous batch of text ended with the following segment:
            
            <ANCHOR_START>
            "{anchor_text}"
            <ANCHOR_END>
            
            Your Task:
            1. LOCATE this specific text block within the first page of the PDF.
            2. IGNORE everything before it.
            3. IGNORE the anchor text itself (do not repeat it).
            4. START your extraction IMMEDIATELY AFTER this anchor text.
            5. Ensure the sentence flow is seamless.
            """
        else:
            instructions = "This is the first batch. Start extraction from the very beginning."

        prompt = f"""
        You are a scientific audiobook editor. Convert this PDF into clean, linear text.

        {instructions}

        STRICT CLEANING RULES:
        1. Remove all headers, footers, page numbers, and running titles.
        2. Remove all Citations (e.g., [1], (Smith 2020)).
        3. Remove Tables and Figures completely.
        4. Join hyphenated words (e.g. "con-\ntext" -> "context").
        5. Output PLAIN TEXT only.
        """

        response_stream = client.models.generate_content_stream(
            model=ai_model, 
            contents=[sample_file, prompt],
            config=types.GenerateContentConfig(temperature=0.1)
        )
        
        chunk_text_parts = []
        print("  AI Processing: ", end="", flush=True)
        
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


# def _process_single_chunk(client, chunk_path, has_context_page):
#     # Helper to process one chunk
#     try:
#         sample_file = client.files.upload(file=chunk_path)
        
#         while sample_file.state.name == "PROCESSING":
#             time.sleep(1)
#             sample_file = client.files.get(name=sample_file.name)
            
#         if sample_file.state.name == "FAILED":
#             return None

#         # prompt based on position
#         context_instruction = ""
#         if has_context_page:
#             context_instruction = "NOTE: The first page of this PDF is overlap from the previous batch. Use it to complete any broken sentences at the start, but DO NOT re-output the full text of the first page."

#         prompt = f"""
#         TASK: Extract a clean, linear reading stream from the attached scientific PDF for Text-to-Speech (TTS) processing.

#         {context_instruction}

#         STRICT EXCLUSION RULES (Do NOT output these):
#         1.  **Headers & Footers**: Remove running titles, page numbers, and author names that appear at the top/bottom of pages.
#         2.  **Citations**: Remove in-text citations entirely. 
#             -   Example Input: "As shown by Smith et al. (2020) and [12]..."
#             -   Target Output: "As shown..." (Remove the references).
#         3.  **Figures & Tables**: Do not describe them. Do not output table data. Skip them entirely.
#         4.  **Meta-text**: Remove "doi:...", email addresses, and "Keywords:".

#         TEXT RECONSTRUCTION RULES:
#         1.  **Hyphenation**: Join words split across lines (e.g., "con-\ntext" -> "context").
#         2.  **Flow**: Output a continuous stream of text. Do not preserve the PDF's line breaks.
#         3.  **Equations**: If an equation is part of a sentence, summarize it as "the equation" or skip it if the sentence stands alone.

#         OUTPUT FORMAT:
#         Return ONLY the raw extracted text. No markdown formatting (no bold/italics), no intro/outro conversational filler.
#         """

#         response_stream = client.models.generate_content_stream(
#             model=ai_model, 
#             contents=[sample_file, prompt],
#             config=types.GenerateContentConfig(temperature=0.1)
#         )
        
#         chunk_text_parts = []
#         print("  Receiving: ", end="", flush=True)
        
#         for chunk in response_stream:
#             print(".", end="", flush=True)
#             if chunk.text:
#                 chunk_text_parts.append(chunk.text)
        
#         try:
#             client.files.delete(name=sample_file.name)
#         except:
#             pass
            
#         return "".join(chunk_text_parts)

#     except Exception as e:
#         print(f"\nError in batch: {e}")
#         return None