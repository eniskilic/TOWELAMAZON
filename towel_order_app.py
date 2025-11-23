import streamlit as st
import pdfplumber
import re
import pandas as pd
from io import BytesIO
from reportlab.lib.pagesizes import landscape, inch
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.utils import simpleSplit
from PyPDF2 import PdfReader, PdfWriter  # <-- for PDF merging

# ─────────────────────────────────────────────────────────────────────────────
# App config & session
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(page_title="Towel Order Parser", layout="wide", page_icon="🧺")
for key in ["mfg_labels_pdf", "gift_notes_pdf", "merged_pdf"]:
    if key not in st.session_state:
        st.session_state[key] = None

# ─────────────────────────────────────────────────────────────────────────────
# Color translations (English → Spanish)
# ─────────────────────────────────────────────────────────────────────────────
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
def get_spanish_color(c): return COLOR_TRANSLATIONS.get((c or "").upper().strip(), c or "")

# ─────────────────────────────────────────────────────────────────────────────
# PDF parser (UPDATED to detect gift card lines)
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
                    'shipping_service': '',
                    'items': []
                }
                m = re.search(r'Order Date:\s*(.+?)(?:\n|Shipping)', text)
                if m: current['order_date'] = m.group(1).strip()
                m = re.search(r'Shipping Service:\s*(.+?)(?:\n|Buyer)', text)
                if m: current['shipping_service'] = m.group(1).strip()
                m = re.search(r'Ship To:\s*\n\s*(.+?)(?:\n)', text)
                if m: current['buyer_name'] = m.group(1).strip()

            if not current: continue
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
                if 'Set-6Pcs' in sku:
                    product_type = '6-pc Set'
                    fields = [
                        ('Small 1', r'First Washcloth:\s*(.+?)(?:\n|Second)'),
                        ('Small 2', r'Second Washcloth:\s*(.+?)(?:\n|First Hand)'),
                        ('Medium 1', r'First Hand Towel:\s*(.+?)(?:\n|Second Hand)'),
                        ('Medium 2', r'Second Hand Towel:\s*(.+?)(?:\n|First Bath)'),
                        ('Large 1', r'First Bath Towel:\s*(.+?)(?:\n|Second Bath)'),
                        ('Large 2', r'Second Bath Towel:\s*(.+?)(?:\n|Item|Grand|Gift|Add|Choose|$)'),
                    ]
                elif 'Set-3Pcs' in sku:
                    product_type = '3-pc Set'
                    fields = [
                        ('Small', r'Washcloth:\s*(.+?)(?:\n|Hand Towel)'),
                        ('Medium', r'Hand Towel:\s*(.+?)(?:\n|Bath Towel)'),
                        ('Large', r'Bath Towel:\s*(.+?)(?:\n|Item|Grand|Gift|Add|$)'),
                    ]
                elif 'HT-2' in sku or 'HT-2PCS' in sku or 'HT-2Pcs' in sku:
                    product_type = '2-pc Hand Towel'
                    fields = [
                        ('Medium 1', r'First Hand Towel:\s*(.+?)(?:\n|Second)'),
                        ('Medium 2', r'Second Hand Towel:\s*(.+?)(?:\n|Item|Grand|Gift|$)'),
                    ]
                elif 'BT-2' in sku or 'BT-2Pcs' in sku:
                    product_type = '2-pc Bath Towel'
                    fields = [
                        ('Large 1', r'First Bath Towel:\s*(.+?)(?:\n|Second)'),
                        ('Large 2', r'Second Bath Towel:\s*(.+?)(?:\n|Item|Grand|Gift|$)'),
                    ]
                elif 'BS-1' in sku or 'BS-1Pcs' in sku:
                    product_type = 'Bath Sheet (Oversized)'
                    fields = [('Bath Sheet', r'Oversized Bath Sheet:\s*(.+?)(?:\n|Item|Grand|Gift|$)')]

                if fields:
                    for lbl, pat in fields:
                        m = re.search(pat, content)
                        if m: custom.append((lbl, m.group(1).strip()))

                # UPDATED: Better gift message detection
                gift = ''
                has_gift_card = False
                
                # 1. Check for "Gift Message:" pattern (Old format)
                m = re.search(r'Gift Message:\s*(.+?)(?:\n|Item|Grand|$)', content)
                if m: 
                    gift = m.group(1).strip()
                    has_gift_card = True

                # 2. Check for "Gift Card Note:" (NEW FORMAT from 1121 pdf)
                m = re.search(r'Gift Card Note:\s*(.+?)(?:\n|Item|Grand|Please CHECK|$)', content)
                if m:
                    gift = m.group(1).strip()
                    has_gift_card = True
                
                # 3. Check for "Add Gift Card - Line 1/2/3:" patterns
                if re.search(r'Add Gift Card - Line [123]:', content, re.IGNORECASE):
                    has_gift_card = True
                    # Try to extract the gift card text
                    gift_lines = []
                    for line_num in [1, 2, 3]:
                        m = re.search(rf'Add Gift Card - Line {line_num}:\s*(.+?)(?:\n|$)', content, re.IGNORECASE)
                        if m and m.group(1).strip():
                            gift_lines.append(m.group(1).strip())
                    if gift_lines:
                        gift = ' '.join(gift_lines)
                
                # 4. Check for explicit "Gift Bag and Gift Note Please!" trigger (Requested Feature)
                if "Gift Bag and Gift Note Please!" in content:
                    has_gift_card = True
                
                # 5. Fallback check
                if not has_gift_card:
                    m = re.search(r'Add Gift Card:\s*(.+?)(?:\n|Item|Grand|$)', content)
                    if m and m.group(1).strip():
                        gift = m.group(1).strip()
                        has_gift_card = True

                current['items'].append({
                    'sku': sku, 'product_type': product_type, 'towel_color': towel_color,
                    'quantity': quantity, 'font': font, 'font_color': font_color,
                    'customizations': custom, 'gift_message': gift,
                    'has_gift_card': has_gift_card
                })

        if current and current['items']: orders.append(current)
    return orders

# ─────────────────────────────────────────────────────────────────────────────
# Layout helpers (fit wrapped text to a fixed-height box)
# ─────────────────────────────────────────────────────────────────────────────
def wrapped_height(items, label_fs, text_fs, width_pts):
    label_lead = label_fs * 1.15
    text_lead  = text_fs  * 1.25
    total = 0
    for i, (_, value) in enumerate(items):
        lines = simpleSplit(value, "Helvetica-BoldOblique", text_fs, width_pts)
        total += label_lead + max(1, len(lines)) * text_lead
        # Add extra spacing between items (except after last item) - REDUCED to 15%
        if i < len(items) - 1:
            total += text_lead * 0.15
    return total, label_lead, text_lead

def fit_fonts(items, width_pts, height_pts, start_label, start_text, min_fs=8):
    label_fs, text_fs = float(start_label), float(start_text)
    for _ in range(24):
        need, label_lead, text_lead = wrapped_height(items, label_fs, text_fs, width_pts)
        if need <= height_pts:
            return label_fs, text_fs, label_lead, text_lead
        scale = max(0.82, height_pts / max(need, 1))
        label_fs = max(min_fs, label_fs * scale)
        text_fs  = max(min_fs,  text_fs  * scale)
        if label_fs == min_fs and text_fs == min_fs:
            return label_fs, text_fs, label_lead, text_lead
    return label_fs, text_fs, label_lead, text_lead

# ─────────────────────────────────────────────────────────────────────────────
# Gift note label
# ─────────────────────────────────────────────────────────────────────────────
def generate_gift_note(c, order_id, buyer_name, gift_message):
    W, H = landscape((4 * inch, 6 * inch))
    margin = 0.4 * inch
    c.setStrokeColor(colors.HexColor('#8B4513')); c.setLineWidth(3)
    c.rect(margin, margin, W - 2*margin, H - 2*margin, stroke=1, fill=0)
    c.setLineWidth(1)
    c.rect(margin + 0.1*inch, margin + 0.1*inch,
           W - 2*margin - 0.2*inch, H - 2*margin - 0.2*inch, stroke=1, fill=0)
    corners = [
        (margin + 0.15*inch, H - margin - 0.15*inch),
        (W - margin - 0.15*inch, H - margin - 0.15*inch),
        (margin + 0.15*inch, margin + 0.15*inch),
        (W - margin - 0.15*inch, margin + 0.15*inch)
    ]
    c.setFont("Helvetica", 16); c.setFillColor(colors.HexColor('#D4A574'))
    for x, y in corners: c.drawCentredString(x, y - 0.05*inch, "❀")
    c.setFont("Helvetica", 20); c.setFillColor(colors.HexColor('#C64A7B'))
    c.drawCentredString(W / 2, H - margin - 0.5*inch, "♥")
    y = H / 2 + 0.3 * inch
    c.setFont("Helvetica-Oblique", 14); c.setFillColor(colors.HexColor('#4A4A4A'))
    max_w = W - 2*margin - 0.8*inch
    lines = simpleSplit(gift_message, "Helvetica-Oblique", 14, max_w)
    for line in lines:
        c.drawCentredString(W / 2, y, line); y -= 0.22 * inch
    c.setFont("Helvetica-Bold", 12); c.setFillColor(colors.HexColor('#8B4513'))
    c.drawCentredString(W / 2, margin + 0.6*inch, f"To: {buyer_name}")
    c.setFont("Helvetica", 7); c.setFillColor(colors.grey)
    c.drawRightString(W - margin - 0.15*inch, margin + 0.2*inch, f"Order: {order_id}")

# ─────────────────────────────────────────────────────────────────────────────
# Manufacturing label renderer (UPDATED with prominent GIFT NOTE at top)
# ─────────────────────────────────────────────────────────────────────────────
def generate_manufacturing_label(c, data):
    W, H = landscape((4 * inch, 6 * inch))
    left, right = 0.25 * inch, (6 * inch) - 0.25 * inch
    y = (4 * inch) - 0.25 * inch

    # PROMINENT GIFT NOTE BANNER AT TOP (if has gift note)
    if data['has_gift_note']:
        banner_height = 0.35 * inch
        banner_y = y
        y -= banner_height  # Move everything else down
        
        # Draw banner box
        c.setFillColor(colors.HexColor('#D32F2F'))
        c.setStrokeColor(colors.HexColor('#B71C1C'))
        c.setLineWidth(3)
        c.rect(left, banner_y - banner_height, right - left, banner_height, stroke=1, fill=1)
        
        # Draw "GIFT NOTE" text
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 20)
        text_y = banner_y - banner_height/2 - 0.07*inch
        c.drawCentredString((left + right) / 2, text_y, "🎁 GIFT NOTE 🎁")

    # Header (moved down if gift note present)
    c.setFont("Helvetica-Bold", 13); c.setFillColor(colors.black)
    c.drawString(left, y, data['buyer'])
    
    if data['item_count'] > 1:
        c.setFont("Helvetica-Bold", 11)
        c.drawRightString(right, y, f"▲ [{data['item_number']} of {data['item_count']}]")

    y -= 0.16*inch
    c.setFont("Helvetica", 11); c.drawString(left, y, f"Order: {data['order_id']}")
    c.setFont("Helvetica", 9);  c.drawRightString(right, y, data['shipping'])
    y -= 0.15*inch
    c.setFont("Helvetica", 9);  c.drawString(left, y, data['date'])
    y -= 0.22*inch
    c.setLineWidth(2); c.line(left, y, right, y); y -= 0.15*inch

    # Two columns
    total_w = right - left
    left_w  = total_w * 0.40
    right_w = total_w * 0.60
    left_right = left + left_w
    right_left = left_right + 0.08*inch

    # Content box heights (reverted to original size)
    MAX_CONTENT_H_IN    = 3.05 if not data['has_gift_note'] else 2.70
    SIX_PC_CONTENT_IN  = 2.95 if not data['has_gift_note'] else 2.60
    THREE_PC_CONTENT_IN= 2.55 if not data['has_gift_note'] else 2.20
    FEW_CONTENT_IN      = 2.35 if not data['has_gift_note'] else 2.00

    n = len(data['customizations'])
    if n >= 6: content_h = SIX_PC_CONTENT_IN * inch
    elif n >= 3: content_h = THREE_PC_CONTENT_IN * inch
    else: content_h = FEW_CONTENT_IN * inch
    content_h = min(content_h, MAX_CONTENT_H_IN * inch)

    content_top = y
    content_bottom = y - content_h

    # Box + divider
    c.setLineWidth(2);   c.rect(left, content_bottom, right-left, content_h, stroke=1, fill=0)
    c.setLineWidth(1.5); c.line(left_right + 0.04*inch, content_top, left_right + 0.04*inch, content_bottom)

    # LEFT column (product specs) - UPDATED WITH QTY BETWEEN DIVIDERS
    col_y = content_top - 0.12*inch
    col_c = left + left_w/2
    c.setFont("Helvetica", 8); c.drawCentredString(col_c, col_y, "PRODUCT:"); col_y -= 0.22*inch
    c.setFont("Helvetica-Bold", 13); c.drawCentredString(col_c, col_y, data['product_type'].upper()); col_y -= 0.26*inch
    c.setFont("Helvetica-Bold", 16); c.drawCentredString(col_c, col_y, data['towel_color'].upper()); col_y -= 0.30*inch
    
    # FIRST DIVIDER (above QTY)
    c.setLineWidth(0.5); c.line(left + 0.05*inch, col_y, left_right - 0.05*inch, col_y); col_y -= 0.22*inch
    
    # QTY in the middle (sandwiched between dividers) - CENTERED
    c.setFont("Helvetica-BoldOblique" if int(data['quantity'])>2 else "Helvetica-Bold", 18)
    c.drawCentredString(col_c, col_y, f"QTY: {data['quantity']}"); col_y -= 0.22*inch
    
    # SECOND DIVIDER (below QTY)
    c.setLineWidth(0.5); c.line(left + 0.05*inch, col_y, left_right - 0.05*inch, col_y); col_y -= 0.24*inch
    
    c.setFont("Helvetica", 8); c.drawCentredString(col_c, col_y, "THREAD COLOR:"); col_y -= 0.2*inch
    c.setFont("Helvetica-Bold", 15); c.drawCentredString(col_c, col_y, data['thread_color'].upper()); col_y -= 0.14*inch
    c.setFont("Helvetica", 12); c.drawCentredString(col_c, col_y, get_spanish_color(data['thread_color']))

    # RIGHT column header
    right_header_y = content_top - 0.12*inch
    c.setFont("Helvetica-Bold", 9)
    c.drawString(right_left + 0.05*inch, right_header_y, "PERSONALIZATION:")

    # Usable area (within the fixed box, with MORE padding after header)
    pad_t, pad_b, pad_r, pad_l = 0.20*inch, 0.10*inch, 0.10*inch, 0.08*inch  # Keep 0.20" after header
    usable_top    = right_header_y - pad_t
    usable_bottom = content_bottom + pad_b
    usable_height = max(1, usable_top - usable_bottom)
    usable_width  = (right - pad_r) - (right_left + pad_l)

    items = data['customizations']
    start_label = 12 if len(items) <= 3 else 11
    start_text  = 16 if len(items) <= 3 else 15
    if len(items) >= 6: start_label, start_text = 10, 14

    label_fs, text_fs, label_lead, text_lead = fit_fonts(
        items, usable_width, usable_height, start_label, start_text, min_fs=8
    )

    # Draw inside the capped box
    x = right_left + pad_l
    ytxt = usable_top
    overflow = False
    for idx, (lbl, val) in enumerate(items):
        if ytxt - label_lead < usable_bottom: overflow=True; break
        c.setFont("Helvetica", label_fs); c.drawString(x, ytxt, f"{lbl}:"); ytxt -= label_lead
        lines = simpleSplit(val, "Helvetica-BoldOblique", text_fs, usable_width)
        for ln in lines:
            if ytxt - text_lead < usable_bottom: overflow=True; break
            c.setFont("Helvetica-BoldOblique", text_fs); c.drawString(x, ytxt, ln); ytxt -= text_lead
        # Add extra spacing between items - REDUCED to 15%
        if idx < len(items) - 1:  # Don't add extra space after last item
            ytxt -= text_lead * 0.15  # 15% spacing between items
        if overflow: break

    if overflow:
        remaining = len(items) - idx
        c.setFont("Helvetica-Oblique", 8)
        c.drawString(x, usable_bottom, f"[+{remaining} more…]")

# ─────────────────────────────────────────────────────────────────────────────
# Analysis & Merging Functions (QC Logic)
# ─────────────────────────────────────────────────────────────────────────────
def analyze_shipping_pdf(pdf_file):
    """Extracts Order IDs from shipping labels to perform QC."""
    shipping_data = []
    with pdfplumber.open(pdf_file) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            # Amazon Order ID regex: 123-1234567-1234567
            m = re.search(r'(\d{3}-\d{7}-\d{7})', text)
            found_id = m.group(1) if m else "Not Found"
            shipping_data.append({
                'page_num': i + 1,
                'found_id': found_id
            })
    return shipping_data

def merge_shipping_and_manufacturing_labels_simple(shipping_pdf_bytes, manufacturing_pdf_bytes, order_dataframe):
    """Simple positional merge: assumes shipping labels are in the same order as parsed data."""
    try:
        shipping_pdf = PdfReader(shipping_pdf_bytes)
        manufacturing_pdf = PdfReader(manufacturing_pdf_bytes)
        
        seen_orders = []
        order_item_counts = []
        
        for order_id in order_dataframe['Order ID']:
            if order_id not in seen_orders:
                seen_orders.append(order_id)
                item_count = len(order_dataframe[order_dataframe['Order ID'] == order_id])
                order_item_counts.append(item_count)
        
        shipping_to_mfg = {}
        mfg_index = 0
        
        for shipping_index, item_count in enumerate(order_item_counts):
            shipping_to_mfg[shipping_index] = list(range(mfg_index, mfg_index + item_count))
            mfg_index += item_count
        
        output_pdf = PdfWriter()
        total_shipping_labels = len(seen_orders)
        
        for ship_idx in range(total_shipping_labels):
            if ship_idx >= len(shipping_pdf.pages): break
            
            output_pdf.add_page(shipping_pdf.pages[ship_idx])
            
            if ship_idx in shipping_to_mfg:
                for mfg_idx in shipping_to_mfg[ship_idx]:
                    if mfg_idx < len(manufacturing_pdf.pages):
                        output_pdf.add_page(manufacturing_pdf.pages[mfg_idx])
        
        output_buffer = BytesIO()
        output_pdf.write(output_buffer)
        output_buffer.seek(0)
        
        return output_buffer, len(seen_orders), sum(len(v) for v in shipping_to_mfg.values())
        
    except Exception as e:
        st.error(f"Error merging labels: {str(e)}")
        return None, 0, 0

# ─────────────────────────────────────────────────────────────────────────────
# Streamlit UI
# ─────────────────────────────────────────────────────────────────────────────
st.title("🧺 Towel Order Parser & Label Generator")
st.markdown("**Upload Amazon packing slip PDFs to generate manufacturing labels**")

uploaded_files = st.file_uploader("Upload PDF files", type=['pdf'], accept_multiple_files=True)

if uploaded_files:
    st.session_state['mfg_labels_pdf'] = None
    st.session_state['gift_notes_pdf'] = None
    st.session_state['merged_pdf'] = None

    all_orders = []
    with st.spinner("Parsing PDFs..."):
        for f in uploaded_files:
            try:
                all_orders.extend(parse_towel_orders(f))
            except Exception as e:
                st.error(f"Error parsing {f.name}: {e}")

    if all_orders:
        rows = []
        for o in all_orders:
            for it in o['items']:
                rows.append({
                    'Order ID': o['order_id'],'Date': o['order_date'],'Buyer': o['buyer_name'],
                    'Shipping': o['shipping_service'],'Product Type': it['product_type'],
                    'Color': it['towel_color'],'Quantity': it['quantity'],'Font': it['font'],
                    'Thread Color': it['font_color'],
                    'Customizations': ' | '.join([f"{l}: {t}" for l,t in it['customizations']]),
                    'Gift Message': 'YES' if it['gift_message'] else 'NO',
                    '_order_obj': o, '_item_obj': it
                })
        df = pd.DataFrame(rows); df.index = range(1, len(df)+1)
        df['item_count'] = df.groupby('Order ID')['Order ID'].transform('count')
        df['item_number'] = df.groupby('Order ID').cumcount() + 1

        st.success(f"✅ Parsed {len(all_orders)} orders with {len(df)} items")

        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "📊 Table View","📋 Manufacturing Plan","🏷️ Manufacturing Labels",
            "🎁 Gift Notes","🔗 Smart Merge (QC)"
        ])

        # ─────────────────────────────────────────────────────────────────────
        # TAB 1: Table + Generate ALL
        # ─────────────────────────────────────────────────────────────────────
        with tab1:
            display_df = df.drop(columns=['_order_obj','_item_obj'])
            st.dataframe(display_df, use_container_width=True, height=420)
            c1, c2 = st.columns(2)
            with c1:
                gen_all = st.button("🏷️ Generate ALL Manufacturing Labels", type="primary", use_container_width=True)
            with c2:
                dl_ph = st.empty()

            if gen_all:
                with st.spinner("Generating all manufacturing labels..."):
                    out = BytesIO(); c = canvas.Canvas(out, pagesize=landscape((4*inch,6*inch)))
                    for _, r in df.iterrows():
                        o, it = r['_order_obj'], r['_item_obj']
                        data = {
                            'order_id': o['order_id'], 'buyer': o['buyer_name'], 'date': o['order_date'],
                            'shipping': o['shipping_service'], 'quantity': it['quantity'],
                            'product_type': it['product_type'], 'towel_color': it['towel_color'],
                            'thread_color': it['font_color'], 'font': it['font'],
                            'customizations': it['customizations'],
                            'has_gift_note': it.get('has_gift_card', bool(it['gift_message'])),
                            'item_number': r['item_number'], 'item_count': r['item_count']
                        }
                        generate_manufacturing_label(c, data); c.showPage()
                    c.save(); out.seek(0)
                    st.session_state['mfg_labels_pdf'] = out.getvalue()
                    st.success(f"✅ Generated {len(df)} manufacturing labels")
                    with dl_ph:
                        st.download_button("📥 Download PDF", st.session_state['mfg_labels_pdf'],
                                           "all_manufacturing_labels.pdf","application/pdf",
                                           use_container_width=True, key="dl_all")

        # ─────────────────────────────────────────────────────────────────────
        # TAB 2: Manufacturing Plan
        # ─────────────────────────────────────────────────────────────────────
        with tab2:
            st.title("🏭 Manufacturing Plan - Color-Based Summary")
            st.markdown("*6-pc sets = 2 production units (2× 3-pc sets)*")
            
            df_mfg = df.copy()
            def units(r): return (int(r['Quantity']) * 2) if '6-pc' in r['Product Type'].lower() else int(r['Quantity'])
            df_mfg['Mfg_Units'] = df_mfg.apply(units, axis=1)
            
            st.header("📊 Executive Summary")
            c1, c2, c3, c4 = st.columns(4)
            with c1: st.metric("Total Orders", len(df['Order ID'].unique()))
            with c2: st.metric("Total Line Items", len(df))
            with c3: st.metric("Production Units", int(df_mfg['Mfg_Units'].sum()))
            with c4: st.metric("Gift Notes", int((df['Gift Message']=='YES').sum()))
            
            st.markdown("---")
            st.header("🎨 Production by Towel Color")
            
            for towel_color in sorted(df_mfg['Color'].unique()):
                color_df = df_mfg[df_mfg['Color'] == towel_color]
                total_color_units = int(color_df['Mfg_Units'].sum())
                
                with st.expander(f"🎨 **{towel_color.upper()}** - {total_color_units} Production Units", expanded=True):
                    st.markdown(f"### {towel_color.upper()}")
                    product_summary = color_df.groupby('Product Type').agg({
                        'Quantity': 'sum',
                        'Mfg_Units': 'sum'
                    }).sort_values('Product Type')
                    
                    for product_type, row in product_summary.iterrows():
                        qty = int(row['Quantity'])
                        prod_units = int(row['Mfg_Units'])
                        
                        if '6-pc' in product_type.lower():
                            st.markdown(f"**6-pc Set:** {qty} sets ({prod_units} production units)")
                        elif '3-pc' in product_type.lower():
                            st.markdown(f"**3-pc Set:** {qty} sets")
                        elif 'Bath Sheet' in product_type:
                            st.markdown(f"**Bath Sheet (Oversized):** {qty} units")
                        elif '2-pc Bath' in product_type:
                            st.markdown(f"**2-pc Bath Towel:** {qty} sets")
                        elif '2-pc Hand' in product_type:
                            st.markdown(f"**2-pc Hand Towel:** {qty} sets")
                        else:
                            st.markdown(f"**{product_type}:** {qty} units")
                    
                    st.markdown(f"**TOTAL PRODUCTION UNITS: {total_color_units}**")
                    st.markdown("---")

        # ─────────────────────────────────────────────────────────────────────
        # TAB 3: Generate selected labels
        # ─────────────────────────────────────────────────────────────────────
        with tab3:
            st.subheader("Manufacturing Labels")
            selected = []
            for idx, row in df.iterrows():
                a,b = st.columns([0.1,0.9])
                with a:
                    if st.checkbox("", key=f"mfg_{idx}"): selected.append(idx)
                with b:
                    gift_indicator = " 🎁" if row['Gift Message'] == 'YES' else ""
                    st.write(f"**{row['Order ID']}** — {row['Product Type']} — {row['Color']} — Qty: {row['Quantity']}{gift_indicator}")
            if selected:
                if st.button("🖨️ Generate Selected Labels", type="primary"):
                    with st.spinner("Generating labels..."):
                        out = BytesIO(); c = canvas.Canvas(out, pagesize=landscape((4*inch,6*inch)))
                        for idx in selected:
                            r = df.loc[idx]; o, it = r['_order_obj'], r['_item_obj']
                            data = {
                                'order_id': o['order_id'], 'buyer': o['buyer_name'], 'date': o['order_date'],
                                'shipping': o['shipping_service'], 'quantity': it['quantity'],
                                'product_type': it['product_type'], 'towel_color': it['towel_color'],
                                'thread_color': it['font_color'], 'font': it['font'],
                                'customizations': it['customizations'],
                                'has_gift_note': it.get('has_gift_card', bool(it['gift_message'])),
                                'item_number': r['item_number'], 'item_count': r['item_count']
                            }
                            generate_manufacturing_label(c, data); c.showPage()
                        c.save(); out.seek(0)
                        st.download_button("📥 Download Manufacturing Labels PDF", out.getvalue(),
                                           "manufacturing_labels.pdf", "application/pdf")
                        st.success(f"✅ Generated {len(selected)} labels")
            else:
                st.info("Select items above to generate labels")

        # ─────────────────────────────────────────────────────────────────────
        # TAB 4: Gift notes
        # ─────────────────────────────────────────────────────────────────────
        with tab4:
            st.subheader("Gift Note Labels")
            gifts = df[df['Gift Message']=='YES']
            if gifts.empty:
                st.info("No orders with gift messages found")
            else:
                st.markdown(f"**{len(gifts)} orders with gift messages**")
                chosen = []
                for idx, row in gifts.iterrows():
                    it = row['_item_obj']; a,b = st.columns([0.1,0.9])
                    with a:
                        if st.checkbox("", key=f"gift_{idx}"): chosen.append(idx)
                    with b:
                        with st.expander(f"**{row['Order ID']}** — {row['Buyer']}"):
                            st.write(f"**Message:** {it['gift_message']}")
                
                # BUTTONS FOR GENERATION
                c1, c2 = st.columns(2)
                
                with c1:
                    if chosen and st.button("🎁 Generate Selected Gift Notes", type="primary"):
                        with st.spinner("Generating gift notes..."):
                            out = BytesIO(); c = canvas.Canvas(out, pagesize=landscape((4*inch,6*inch)))
                            for idx in chosen:
                                r = gifts.loc[idx]; o, it = r['_order_obj'], r['_item_obj']
                                generate_gift_note(c, o['order_id'], o['buyer_name'], it['gift_message'])
                                c.showPage()
                            c.save(); out.seek(0)
                            st.session_state['gift_notes_pdf'] = out.getvalue()
                            st.download_button("📥 Download Selected Gift Notes PDF", out.getvalue(),
                                            "gift_notes_selected.pdf","application/pdf")
                
                with c2:
                    if st.button("🎁 Generate ALL Gift Notes"):
                        with st.spinner("Generating ALL gift notes..."):
                            out = BytesIO(); c = canvas.Canvas(out, pagesize=landscape((4*inch,6*inch)))
                            for idx, row in gifts.iterrows():
                                o, it = row['_order_obj'], row['_item_obj']
                                generate_gift_note(c, o['order_id'], o['buyer_name'], it['gift_message'])
                                c.showPage()
                            c.save(); out.seek(0)
                            st.session_state['gift_notes_pdf'] = out.getvalue()
                            st.download_button("📥 Download ALL Gift Notes PDF", out.getvalue(),
                                            "gift_notes_all.pdf","application/pdf")

        # ─────────────────────────────────────────────────────────────────────
        # TAB 5: SMART MERGE (QC)
        # ─────────────────────────────────────────────────────────────────────
        with tab5:
            st.subheader("🔗 Smart Merge with QC (Quality Control)")
            st.info("This tool will analyze your Shipping PDF to ensure labels match your orders exactly.")

            ship_pdf = st.file_uploader("1️⃣ Upload Shipping Labels PDF", type=["pdf"], key="ship_pdf_qc")
            
            if 'qc_complete' not in st.session_state: st.session_state.qc_complete = False
            
            if ship_pdf:
                if st.button("2️⃣ Analyze & Compare", type="primary"):
                    with st.spinner("Scanning shipping labels..."):
                        # 1. Extract info from Shipping PDF
                        ship_pdf.seek(0)
                        shipping_data = analyze_shipping_pdf(ship_pdf)
                        
                        # 2. Get Unique Orders from Parsed Data
                        unique_orders = df[['Order ID', 'Buyer']].drop_duplicates().reset_index(drop=True)
                        
                        # 3. Build QC Table
                        qc_rows = []
                        all_match = True
                        
                        max_len = max(len(shipping_data), len(unique_orders))
                        
                        for i in range(max_len):
                            ship_info = shipping_data[i] if i < len(shipping_data) else {'found_id': 'MISSING PAGE'}
                            order_info = unique_orders.iloc[i] if i < len(unique_orders) else {'Order ID': 'MISSING DATA', 'Buyer': ''}
                            
                            # Check Match
                            match = False
                            if ship_info['found_id'] == order_info['Order ID']:
                                match = True
                            elif ship_info['found_id'] == 'Not Found':
                                match = "⚠️ Unreadable" # Image label?
                            else:
                                match = False
                                
                            qc_rows.append({
                                'Seq #': i + 1,
                                'Shipping Label ID': ship_info['found_id'],
                                'Packing Slip Order ID': order_info['Order ID'],
                                'Buyer Name': order_info['Buyer'],
                                'Status': match
                            })
                            
                            if match is False: all_match = False

                        st.session_state.qc_rows = qc_rows
                        st.session_state.qc_match = all_match
                        st.session_state.qc_complete = True

            if st.session_state.get('qc_complete'):
                st.write("### 🧐 Analysis Results")
                
                # Summary Metrics
                n_ship = len(st.session_state.qc_rows)
                n_orders = len(df['Order ID'].unique())
                
                c1, c2, c3 = st.columns(3)
                c1.metric("Shipping Labels", n_ship)
                c2.metric("Packing Slip Orders", n_orders)
                
                if n_ship == n_orders:
                    c3.success("✅ Counts Match")
                else:
                    c3.error("❌ Counts Mismatch")

                # QC Table Display
                def highlight_status(val):
                    if val is True: return "background-color: #d4edda; color: #155724" # Green
                    if val == "⚠️ Unreadable": return "background-color: #fff3cd; color: #856404" # Yellow
                    return "background-color: #f8d7da; color: #721c24" # Red

                qc_df = pd.DataFrame(st.session_state.qc_rows)
                st.dataframe(qc_df.style.applymap(highlight_status, subset=['Status']), use_container_width=True)

                # Warning if IDs mismatch
                if not st.session_state.qc_match:
                    st.warning("⚠️ Some Order IDs do not match or could not be read. Please verify the table above.")
                    st.write("If the IDs say 'Not Found', it might be an image-based label. Check if the Sequence matches.")

                st.write("---")
                st.write("### 3️⃣ Finalize Merge")
                
                # MERGE BUTTON SECTION
                if st.button("✅ Confirm & Merge Labels", type="primary"):
                    # Generate manufacturing labels if not already done
                    if not st.session_state['mfg_labels_pdf']:
                        with st.spinner("Auto-generating manufacturing labels..."):
                            out = BytesIO(); c = canvas.Canvas(out, pagesize=landscape((4*inch,6*inch)))
                            for _, r in df.iterrows():
                                o, it = r['_order_obj'], r['_item_obj']
                                data = {
                                    'order_id': o['order_id'], 'buyer': o['buyer_name'], 'date': o['order_date'],
                                    'shipping': o['shipping_service'], 'quantity': it['quantity'],
                                    'product_type': it['product_type'], 'towel_color': it['towel_color'],
                                    'thread_color': it['font_color'], 'font': it['font'],
                                    'customizations': it['customizations'],
                                    'has_gift_note': it.get('has_gift_card', bool(it['gift_message'])),
                                    'item_number': r['item_number'], 'item_count': r['item_count']
                                }
                                generate_manufacturing_label(c, data); c.showPage()
                            c.save(); out.seek(0)
                            st.session_state['mfg_labels_pdf'] = out.getvalue()

                    # Perform Merge
                    ship_pdf.seek(0)
                    merged_buffer, n_s, n_m = merge_shipping_and_manufacturing_labels_simple(
                        ship_pdf,
                        BytesIO(st.session_state['mfg_labels_pdf']),
                        df
                    )
                    
                    if merged_buffer:
                        st.success(f"🎉 Merged {n_s} Shipping Labels with {n_m} Manufacturing Labels!")
                        st.download_button(
                            "📥 Download Final Merged PDF", 
                            merged_buffer, 
                            "FINAL_MERGED_LABELS.pdf", 
                            "application/pdf",
                            type="primary",
                            use_container_width=True
                        )

else:
    st.info("👆 Upload PDF files (packing slips) to get started")
