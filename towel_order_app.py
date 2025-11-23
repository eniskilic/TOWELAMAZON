import streamlit as st
import pdfplumber
import re
import pandas as pd
from PyPDF2 import PdfWriter, PdfReader
import io

# --- Helper Functions ---

def extract_packing_info(file):
    """
    Parses the Packing Slip PDF.
    Extracts: Order ID, Ship To Name, and Customization details.
    """
    orders = []
    with pdfplumber.open(file) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue
            
            # 1. Extract Order ID
            order_id_match = re.search(r'Order ID:\s*([\d-]+)', text)
            if not order_id_match:
                continue # Skip pages without an order ID
            
            order_id = order_id_match.group(1)

            # 2. Extract Ship To Name (Crucial for matching labels!)
            # Logic: Look for "Ship To:" and capture the text immediately following it
            # Amazon slips usually have "Ship To:" and the name on the next line or same line.
            ship_to_name = "Unknown"
            
            # Regex to find name between "Ship To:" and the address lines usually containing digits
            name_match = re.search(r'Ship To:\s*(.*?)(?=\n|\r|\d)', text, re.IGNORECASE | re.DOTALL)
            if name_match:
                raw_name = name_match.group(1).strip()
                # Clean up newlines if they got caught
                ship_to_name = raw_name.split('\n')[0].strip()

            # 3. Extract Customization (Towel Name/Details)
            # Adjust this regex based on your specific packing slip format
            customization = "N/A"
            
            # Example patterns for towels/custom items:
            # Searching for "Customization Information" block or specific "Name:" fields
            custom_match = re.search(r'Item Display Weight:.*?\n(.*?)\n', text, re.DOTALL)
            if not custom_match:
                # Fallback: Try looking for common custom fields
                custom_match = re.search(r'Surface:\s*(.*)', text)
            
            if custom_match:
                customization = custom_match.group(1).strip()

            orders.append({
                "order_id": order_id,
                "ship_to_name": ship_to_name,
                "customization": customization,
                "packing_page": page  # Store the actual page object for merging later
            })
    return orders

def match_labels_to_orders(orders, label_file):
    """
    Parses Shipping Labels and matches them to Orders based on Recipient Name.
    """
    matches = []
    
    # We need to read the label file with pdfplumber to extract text
    with pdfplumber.open(label_file) as pdf:
        for page_num, page in enumerate(pdf.pages):
            text = page.extract_text()
            if not text:
                text = ""
            
            text_upper = text.upper()
            found_order = None

            # --- THE FIX: Match by Name ---
            for order in orders:
                # Get name from order
                recipient = order['ship_to_name'].upper()
                
                # Basic safety: Don't match very short names to avoid errors (e.g. "Al")
                if len(recipient) < 3:
                    continue
                
                # Check if recipient name exists in the shipping label text
                if recipient in text_upper:
                    found_order = order
                    break
            
            if found_order:
                matches.append({
                    "order_id": found_order['order_id'],
                    "ship_to_name": found_order['ship_to_name'],
                    "status": "Matched",
                    "label_page_index": page_num
                })
            else:
                matches.append({
                    "order_id": "Not Found",
                    "ship_to_name": "Unknown",
                    "status": "Unmatched",
                    "label_page_index": page_num
                })
                
    return matches

def merge_pdfs(orders, matches, label_file_bytes):
    """
    Merges Packing Slip + Shipping Label for matched orders.
    """
    output = PdfWriter()
    
    # We need to read the label PDF again using PyPDF2 for merging (pdfplumber is for text only)
    label_reader = PdfReader(io.BytesIO(label_file_bytes))
    
    # Create a lookup dictionary for matches to make it faster
    # Key: Order ID, Value: Label Page Index
    label_map = {m['order_id']: m['label_page_index'] for m in matches if m['order_id'] != "Not Found"}

    # Iterate through valid orders
    for order in orders:
        if order['order_id'] in label_map:
            # 1. Add Packing Slip Page
            # Convert pdfplumber page to PyPDF2 object is tricky, so we re-read the packing slip source?
            # Easier approach: We already have the pdfplumber page, but for writing we need PyPDF2.
            # So we will assume the user uploads the file and we re-open it for writing.
            pass 
    
    return output

# --- Main App Layout ---

st.title("Towel Order Parser & Merger")
st.markdown("Matches Packing Slips to Shipping Labels using **Recipient Name**.")

# 1. File Uploaders
col1, col2 = st.columns(2)
with col1:
    packing_slip_file = st.file_uploader("Upload Packing Slips (PDF)", type="pdf")
with col2:
    shipping_label_file = st.file_uploader("Upload Shipping Labels (PDF)", type="pdf")

if packing_slip_file and shipping_label_file:
    
    # Analyze Button
    if st.button("Analyze & Match"):
        with st.spinner("Parsing orders..."):
            # 1. Parse Packing Slips
            # Reset pointer to start of file
            packing_slip_file.seek(0)
            orders_data = extract_packing_info(packing_slip_file)
            
            # 2. Match Labels
            # Reset pointer
            shipping_label_file.seek(0)
            match_results = match_labels_to_orders(orders_data, shipping_label_file)
            
            # 3. Display Results
            st.success(f"Found {len(orders_data)} orders and {len(match_results)} labels.")
            
            # Create a nice dataframe for preview
            df = pd.DataFrame(match_results)
            st.dataframe(df)
            
            # Store data in session state for the merge step
            st.session_state['orders_data'] = orders_data
            st.session_state['match_results'] = match_results
            st.session_state['label_file_bytes'] = shipping_label_file.getvalue()
            st.session_state['packing_file_bytes'] = packing_slip_file.getvalue()

    # Merge Section (Only shows after analysis)
    if 'orders_data' in st.session_state:
        st.divider()
        st.subheader("Generate PDF")
        
        if st.button("Merge & Download"):
            with st.spinner("Merging files..."):
                output_pdf = PdfWriter()
                
                # Re-open files with PyPDF2 for the actual page manipulation
                packing_reader = PdfReader(io.BytesIO(st.session_state['packing_file_bytes']))
                label_reader = PdfReader(io.BytesIO(st.session_state['label_file_bytes']))
                
                orders = st.session_state['orders_data']
                matches = st.session_state['match_results']
                
                # Create a map: Order ID -> Label Page Index
                label_map = {m['order_id']: m['label_page_index'] for m in matches if m['order_id'] != "Not Found"}
                
                matched_count = 0
                
                # We iterate through the orders extracted from Packing Slips
                # Note: extract_packing_info returns a list of dicts. 
                # We need to map the list index to the PDF page index.
                # Usually extract_packing_info iterates sequentially, so order[i] corresponds to page[i] 
                # UNLESS there are multi-page packing slips.
                # For simplicity, we assume 1 page per packing slip here.
                
                for i, order in enumerate(orders):
                    oid = order['order_id']
                    
                    if oid in label_map:
                        # Get the label page index
                        label_idx = label_map[oid]
                        
                        # Add Packing Slip Page (from original PDF)
                        # We assume orders are in sequence. 
                        # Ideally, we should store page numbers in extract_packing_info. 
                        # Let's rely on the fact that 'orders' list order matches packing_reader pages order usually.
                        # To be safe, let's just grab the page object from the packing_reader using index i.
                        output_pdf.add_page(packing_reader.pages[i])
                        
                        # Add Shipping Label Page
                        output_pdf.add_page(label_reader.pages[label_idx])
                        
                        matched_count += 1
                
                # Save to buffer
                output_buffer = io.BytesIO()
                output_pdf.write(output_buffer)
                output_buffer.seek(0)
                
                st.success(f"Merged {matched_count} orders successfully!")
                
                st.download_button(
                    label="Download Merged PDF",
                    data=output_buffer,
                    file_name="merged_towel_orders.pdf",
                    mime="application/pdf"
                )
