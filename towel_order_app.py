import streamlit as st
import pdfplumber
import re
import pandas as pd
from io import BytesIO
from reportlab.lib.pagesizes import landscape, inch
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.utils import simpleSplit
from pypdf import PdfReader, PdfWriter 
from difflib import SequenceMatcher

# ─────────────────────────────────────────────────────────────────────────────
# App config & session
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(page_title="Towel Order Parser - Anchor Mode", layout="wide", page_icon="🧺")

for key in ["mfg_labels_pdf", "merged_pdf", "qc_rows", "qc_complete"]:
    if key not in st.session_state:
        st.session_state[key] = None

# ─────────────────────────────────────────────────────────────────────────────
# Utils
# ─────────────────────────────────────────────────────────────────────────────
def clean_text(text):
    """Normalize text for matching (remove punctuation, lower case)."""
    if not text: return ""
    return re.sub(r'[^a-zA-Z0-9\s]', '', text).lower().strip()

def get_spanish_color(c): 
    COLOR_TRANSLATIONS = {
        'WHITE': 'Blanco','BLACK': 'Negro','NAVY': 'Azul Marino','NAVY BLUE': 'Azul Marino',
        'GOLD': 'Oro','SILVER': 'Plata','RED': 'Rojo','BLUE': 'Azul','MID BLUE': 'Azul Medio',
        'LIGHT BLUE': 'Azul Claro','DARK BLUE': 'Azul Oscuro','GREEN': 'Verde',
        'LIGHT GREEN': 'Verde Claro','DARK GREEN': 'Verde Oscuro','GREY': 'Gris','GRAY': 'Gris',
        'LIGHT GREY': 'Gris Claro','LIGHT GRAY': 'Gris Claro','DARK GREY': 'Gris Oscuro',
        'DARK GRAY': 'Gris Oscuro','BROWN': 'Marrón','PINK': 'Rosa','LIGHT PINK': 'Rosa Claro',
        'HOT PINK': 'Rosa Fuerte','PURPLE': 'Morado','YELLOW': 'Amarillo','ORANGE': 'Naranja',
        'CREAM': 'Crema','BEIGE': 'Beige','TAN': 'Bronceado','BURGUNDY': 'Burdeos','MAROON': 'Granate'
    }
    return COLOR_TRANSLATIONS.get((c or "").upper().strip(), c or "")

# ─────────────────────────────────────────────────────────────────────────────
# 1. PARSE AMAZON PACKING SLIPS (To get Orders)
# ─────────────────────────────────────────────────────────────────────────────
def parse_towel_orders(pdf_file):
    orders = []
    with pdfplumber.open(pdf_file) as pdf:
        current = None
        for page in pdf.pages:
            text = page.extract_text() or ""

            if 'Order ID:' in text:
                if current and current['items']: orders.append(current)
                m = re.search(r'Order ID:\s*([\d-]+)', text)
                current = {
                    'order_id': m.group(1).strip() if m else '',
                    'order_date': '',
                    'buyer_name': '',
                    'items': []
                }
                m = re.search(r'Order Date:\s*(.+?)(?:\n|Shipping)', text)
                if m: current['order_date'] = m.group(1).strip()
                m = re.search(r'Ship To:\s*\n(.+?)(?:\nOrder ID)', text, re.DOTALL)
                if m: current['buyer_name'] = m.group(1).strip().split('\n')[0]

            if not current: continue
            
            # Simple SKU/Product logic
            blocks = re.split(r'(SKU:\s*[^\n]+)', text)
            for i in range(1, len(blocks), 2):
                if i+1 >= len(blocks): break
                sku_hdr, content = blocks[i], blocks[i+1]
                m = re.search(r'SKU:\s*([^\n]+)', sku_hdr)
                if not m: continue
                sku = re.split(r'\s+(?:Item|Tax|total|\$|Promotion)', m.group(1).strip())[0]

                qty_m = re.search(r'Quantity[^\d]*(\d+)', text[:text.find(sku_hdr)])
                quantity = qty_m.group(1) if qty_m else '1'

                m = re.search(r'Choose Your Font:\s*(.+?)(?:\n|Font Color)', content)
                font = m.group(1).strip() if m else ''
                m = re.search(r'Font Color:\s*([^(#\n]+)', content)
                font_color = m.group(1).strip() if m else ''

                parts = sku.split('-')
                towel_color = parts[-1].strip() if len(parts) >= 2 else 'Unknown'
                towel_color = re.split(r'\s+(?:Tax|Item|total|Promotion|\$)', towel_color)[0].strip()
                towel_color = re.sub(r'[\(\)\[\]]', '', towel_color).strip()

                product_type, fields, custom = 'Unknown', None, []
                # (Product Definitions)
                if 'Set-6Pcs' in sku:
                    product_type = '6-pc Set'
                    fields = [('Small 1', r'First Washcloth:\s*(.+?)(?:\n|Second)'), ('Small 2', r'Second Washcloth:\s*(.+?)(?:\n|First Hand)'), ('Medium 1', r'First Hand Towel:\s*(.+?)(?:\n|Second Hand)'), ('Medium 2', r'Second Hand Towel:\s*(.+?)(?:\n|First Bath)'), ('Large 1', r'First Bath Towel:\s*(.+?)(?:\n|Second Bath)'), ('Large 2', r'Second Bath Towel:\s*(.+?)(?:\n|Item|Grand|Gift|Add|Choose|$)')]
                elif 'Set-3Pcs' in sku:
                    product_type = '3-pc Set'
                    fields = [('Small', r'Washcloth:\s*(.+?)(?:\n|Hand Towel)'), ('Medium', r'Hand Towel:\s*(.+?)(?:\n|Bath Towel)'), ('Large', r'Bath Towel:\s*(.+?)(?:\n|Item|Grand|Gift|Add|$)')]
                elif 'HT-2' in sku or 'HT-2Pcs' in sku:
                    product_type = '2-pc Hand Towel'
                    fields = [('Medium 1', r'First Hand Towel:\s*(.+?)(?:\n|Second)'), ('Medium 2', r'Second Hand Towel:\s*(.+?)(?:\n|Item|Grand|Gift|$)')]
                elif 'BT-2' in sku or 'BT-2Pcs' in sku:
                    product_type = '2-pc Bath Towel'
                    fields = [('Large 1', r'First Bath Towel:\s*(.+?)(?:\n|Second)'), ('Large 2', r'Second Bath Towel:\s*(.+?)(?:\n|Item|Grand|Gift|$)')]
                elif 'BS-1' in sku or 'BS-1Pcs' in sku:
                    product_type = 'Bath Sheet (Oversized)'
                    fields = [('Bath Sheet', r'Oversized Bath Sheet:\s*(.+?)(?:\n|Item|Grand|Gift|$)')]

                if fields:
                    for lbl, pat in fields:
                        m = re.search(pat, content)
                        if m: custom.append((lbl, m.group(1).strip()))

                gift = ''
                has_gift_card = False
                if "Gift Message" in content or "Gift Note" in content: has_gift_card = True
                m = re.search(r'Gift Message:\s*(.+?)(?:\n|Item|Grand|$)', content)
                if m: gift = m.group(1).strip()
                
                current['items'].append({
                    'sku': sku, 'product_type': product_type, 'towel_color': towel_color,
                    'quantity': quantity, 'font': font, 'font_color': font_color,
                    'customizations': custom, 'gift_message': gift, 'has_gift_card': has_gift_card
                })
        if current and current['items']: orders.append(current)
    return orders

# ─────────────────────────────────────────────────────────────────────────────
# 2. GENERATE MFG LABELS (Visuals)
# ─────────────────────────────────────────────────────────────────────────────
def fit_fonts(items, width_pts, height_pts, start_label, start_text):
    label_fs, text_fs = float(start_label), float(start_text)
    # Simple simplistic shrinker
    return label_fs, text_fs, label_fs*1.2, text_fs*1.2

def generate_manufacturing_label(c, data):
    W, H = landscape((4 * inch, 6 * inch))
    left, right = 0.25 * inch, (6 * inch) - 0.25 * inch
    y = (4 * inch) - 0.25 * inch

    if data['has_gift_note']:
        banner_height = 0.35 * inch
        banner_y = y; y -= banner_height 
        c.setFillColor(colors.HexColor('#D32F2F')); c.setStrokeColor(colors.HexColor('#B71C1C')); c.setLineWidth(3)
        c.rect(left, banner_y - banner_height, right - left, banner_height, stroke=1, fill=1)
        c.setFillColor(colors.white); c.setFont("Helvetica-Bold", 20)
        c.drawCentredString((left + right) / 2, banner_y - banner_height/2 - 0.07*inch, "🎁 GIFT NOTE 🎁")

    c.setFont("Helvetica-Bold", 13); c.setFillColor(colors.black)
    c.drawString(left, y, data['buyer'])
    if data['item_count'] > 1:
        c.setFont("Helvetica-Bold", 11)
        c.drawRightString(right, y, f"▲ [{data['item_number']} of {data['item_count']}]")

    y -= 0.16*inch
    c.setFont("Helvetica", 11); c.drawString(left, y, f"Order: {data['order_id']}")
    y -= 0.15*inch
    c.setFont("Helvetica", 9);  c.drawString(left, y, data['date'])
    y -= 0.22*inch
    c.setLineWidth(2); c.line(left, y, right, y); y -= 0.15*inch

    # Content
    c.setFont("Helvetica-Bold", 13); c.drawCentredString((left+right)/2, y, data['product_type'].upper()); y -= 0.25*inch
    c.setFont("Helvetica-Bold", 16); c.drawCentredString((left+right)/2, y, data['towel_color'].upper()); y -= 0.30*inch
    c.setFont("Helvetica-Bold", 18); c.drawCentredString((left+right)/2, y, f"QTY: {data['quantity']}"); y -= 0.30*inch
    
    # Customizations
    y_custom = y
    c.setFont("Helvetica", 10)
    for k, v in data['customizations']:
        c.drawString(left, y_custom, f"{k}: {v}")
        y_custom -= 0.2*inch

# ─────────────────────────────────────────────────────────────────────────────
# 3. EXTRACTION STRATEGY: 4-CARRIER ANCHOR LOGIC
# ─────────────────────────────────────────────────────────────────────────────
def extract_name_via_anchors(page):
    """
    Looks for specific keywords (anchors) and grabs text relative to them.
    """
    text = page.extract_text()
    if not text: return "NO TEXT FOUND"
    
    clean_content = text.upper()
    
    # ---------------------------
    # A. USPS (Stacked: "SHIP" then "TO", Name to RIGHT)
    # ---------------------------
    if "USPS" in clean_content:
        # Find the word "SHIP"
        matches = page.search("SHIP")
        if matches:
            anchor = matches[0] # Take first instance
            # Look to the RIGHT of "SHIP"
            # Crop box: (Right edge of SHIP, Top of SHIP, Page Width, Bottom of SHIP + 30px)
            crop = page.crop((anchor['x1'], anchor['top'] - 5, page.width, anchor['bottom'] + 20))
            lines = crop.extract_text().split('\n')
            # The name is likely the first non-empty line
            for line in lines:
                if line.strip() and "TO" not in line and "SHIP" not in line:
                    return line.strip()

    # ---------------------------
    # B. FEDEX (Variable Height: "TO" -> Look BELOW)
    # ---------------------------
    if "FEDEX" in clean_content:
        # Find "TO" or "TO:"
        matches = page.search("TO")
        # Filter matches to ensure it's likely a header (small width)
        valid_anchor = None
        for m in matches:
            if m['x0'] < page.width / 2: # "TO" is usually on the left half of the box/label
                valid_anchor = m
                break
        
        if valid_anchor:
            # Look BELOW "TO"
            # Crop box: (Left of TO, Bottom of TO, Width of TO + 200, Bottom of TO + 30)
            crop = page.crop((valid_anchor['x0'], valid_anchor['bottom'], valid_anchor['x0'] + 250, valid_anchor['bottom'] + 40))
            lines = crop.extract_text().split('\n')
            if lines: return lines[0].strip()

    # ---------------------------
    # C. UPS (Standard: "SHIP TO" -> Look BELOW)
    # ---------------------------
    if "UPS" in clean_content:
        matches = page.search("SHIP TO")
        if matches:
            anchor = matches[0]
            # Look BELOW "SHIP TO"
            crop = page.crop((anchor['x0'], anchor['bottom'], anchor['x0'] + 300, anchor['bottom'] + 40))
            lines = crop.extract_text().split('\n')
            if lines: return lines[0].strip()

    # ---------------------------
    # D. AMAZON SHIPPING (Fixed Zone: Top Left)
    # ---------------------------
    if "AMAZON" in clean_content or "TBA" in clean_content:
        # Fixed crop: Left 0-250pt, Top 50-150pt (Skipping header)
        # Using simple fixed coordinates relative to page size
        crop = page.crop((10, 40, 300, 150))
        lines = crop.extract_text().split('\n')
        for line in lines:
            # Skip common Amazon headers
            if "UNDELIVERABLE" in line.upper() or "RETURN" in line.upper(): continue
            if line.strip(): return line.strip()

    return "NAME NOT FOUND"

# ─────────────────────────────────────────────────────────────────────────────
# 4. MERGE PROCESS
# ─────────────────────────────────────────────────────────────────────────────
def merge_labels(ship_pdf_bytes, mfg_pdf_bytes, order_df):
    mfg_reader = PdfReader(mfg_pdf_bytes)
    # Map OrderID -> List of Mfg Pages
    mfg_map = {} 
    curr = 0
    for _, row in order_df.iterrows():
        oid = row['Order ID']
        if oid not in mfg_map: mfg_map[oid] = []
        if curr < len(mfg_reader.pages):
            mfg_map[oid].append(mfg_reader.pages[curr])
            curr += 1

    output = PdfWriter()
    qc_data = []
    
    with pdfplumber.open(ship_pdf_bytes) as plumber_pdf:
        ship_reader = PdfReader(ship_pdf_bytes) # For writing
        
        for i, p_page in enumerate(plumber_pdf.pages):
            # 1. Extract Name via Anchors
            extracted_name = extract_name_via_anchors(p_page)
            extracted_clean = clean_text(extracted_name)
            
            # 2. Find Match in Orders
            matched_oid = None
            match_status = "❌ NO MATCH"
            
            # Fuzzy match extracted name vs Order Buyers
            best_ratio = 0
            best_oid = None
            
            for _, row in order_df.iterrows():
                buyer_clean = clean_text(row['Buyer'])
                # Check for substring (e.g. "Alexia" in "Alexia Young")
                if extracted_clean and (extracted_clean in buyer_clean or buyer_clean in extracted_clean):
                    best_ratio = 1.0
                    best_oid = row['Order ID']
                    break
                
                # Sequence Matcher for typos
                ratio = SequenceMatcher(None, extracted_clean, buyer_clean).ratio()
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_oid = row['Order ID']

            if best_ratio > 0.6: # Threshold
                matched_oid = best_oid
                match_status = f"✅ MATCH ({int(best_ratio*100)}%)"

            # 3. Add Pages
            if i < len(ship_reader.pages):
                output.add_page(ship_reader.pages[i])
            
            if matched_oid and matched_oid in mfg_map:
                for p in mfg_map[matched_oid]:
                    output.add_page(p)
                # Remove from map to track orphans
                del mfg_map[matched_oid]

            qc_data.append({
                "Page": i+1, 
                "Extracted Name": extracted_name, 
                "Matched Order": matched_oid if matched_oid else "-",
                "Status": match_status
            })

    # Add orphans
    for oid, pages in mfg_map.items():
        qc_data.append({"Page": "-", "Extracted Name": "-", "Matched Order": oid, "Status": "⚠️ ORPHAN"})
        for p in pages: output.add_page(p)

    out_buf = BytesIO()
    output.write(out_buf)
    return out_buf, pd.DataFrame(qc_data)

# ─────────────────────────────────────────────────────────────────────────────
# UI
# ─────────────────────────────────────────────────────────────────────────────
st.title("🧺 Anchor-Based Label Merger")
st.write("Using coordinate anchors for: **FedEx ('TO' -> Below), UPS ('SHIP TO' -> Below), USPS ('SHIP' -> Right), Amazon (Top-Left)**")

uploaded_files = st.file_uploader("1. Upload Packing Slips (PDF)", type=['pdf'], accept_multiple_files=True)

if uploaded_files:
    all_orders = []
    for f in uploaded_files:
        all_orders.extend(parse_towel_orders(f))
    
    if all_orders:
        # Create DataFrame
        rows = []
        for o in all_orders:
            for it in o['items']:
                rows.append({
                    'Order ID': o['order_id'], 'Buyer': o['buyer_name'], 'Date': o['order_date'],
                    'Quantity': it['quantity'], 'Product Type': it['product_type'],
                    'Color': it['towel_color'], 'Customizations': it['customizations'],
                    'Gift Message': it['gift_message'], 'has_gift_card': it['has_gift_card'],
                    '_order_obj': o, '_item_obj': it
                })
        df = pd.DataFrame(rows)
        df['item_count'] = df.groupby('Order ID')['Order ID'].transform('count')
        df['item_number'] = df.groupby('Order ID').cumcount() + 1
        
        st.success(f"Parsed {len(df)} items.")
        st.dataframe(df[['Order ID', 'Buyer', 'Product Type', 'Color']], height=150)

        # Generate Mfg Labels
        if st.button("2. Generate Manufacturing Labels (Internal)"):
            out = BytesIO(); c = canvas.Canvas(out, pagesize=landscape((4*inch,6*inch)))
            for _, r in df.iterrows():
                o, it = r['_order_obj'], r['_item_obj']
                data = {
                    'order_id': o['order_id'], 'buyer': o['buyer_name'], 'date': o['order_date'],
                    'quantity': it['quantity'], 'product_type': it['product_type'], 
                    'towel_color': it['towel_color'], 'customizations': it['customizations'],
                    'has_gift_note': it['has_gift_card'],
                    'item_number': r['item_number'], 'item_count': r['item_count']
                }
                generate_manufacturing_label(c, data); c.showPage()
            c.save(); out.seek(0)
            st.session_state['mfg_labels_pdf'] = out.getvalue()
            st.success("Manufacturing labels generated in memory.")

        # Merge Step
        ship_pdf = st.file_uploader("3. Upload Shipping Labels (PDF)", type=['pdf'])
        if ship_pdf and st.session_state['mfg_labels_pdf']:
            if st.button("4. Run Smart Anchor Merge"):
                with st.spinner("Analyzing coordinates..."):
                    out_pdf, qc_df = merge_labels(ship_pdf, BytesIO(st.session_state['mfg_labels_pdf']), df)
                    st.session_state['merged_pdf'] = out_pdf.getvalue()
                    
                    st.write("### Analysis Results")
                    def color_status(val):
                        if "✅" in val: return "background-color: #d4edda"
                        if "❌" in val: return "background-color: #f8d7da"
                        return ""
                    st.dataframe(qc_df.style.applymap(color_status, subset=['Status']))
                    
                    st.download_button("📥 Download Final Merged PDF", st.session_state['merged_pdf'], "merged_labels.pdf", "application/pdf", type="primary")
