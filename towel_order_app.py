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
                        ('Medium 2', r'Second Hand Towel:\s*(.+?)(?:\n|Item|Grand|$)'),
                    ]
                elif 'BT-2' in sku or 'BT-2Pcs' in sku:
                    product_type = '2-pc Bath Towel'
                    fields = [
                        ('Large 1', r'First Bath Towel:\s*(.+?)(?:\n|Second)'),
                        ('Large 2', r'Second Bath Towel:\s*(.+?)(?:\n|Item|Grand|$)'),
                    ]
                elif 'BS-1' in sku or 'BS-1Pcs' in sku:
                    product_type = 'Bath Sheet (Oversized)'
                    fields = [('Bath Sheet', r'Oversized Bath Sheet:\s*(.+?)(?:\n|Item|Grand|$)')]

                if fields:
                    for lbl, pat in fields:
                        m = re.search(pat, content)
                        if m: custom.append((lbl, m.group(1).strip()))

                # UPDATED: Better gift message detection
                gift = ''
                has_gift_card = False
                
                # Check for "Gift Message:" pattern
                m = re.search(r'Gift Message:\s*(.+?)(?:\n|Item|Grand|$)', content)
                if m: 
                    gift = m.group(1).strip()
                    has_gift_card = True
                
                # Check for "Add Gift Card - Line 1/2/3:" patterns
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
                
                # Fallback check
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
        # Add extra spacing between items (except after last item) - back to 50%
        if i < len(items) - 1:
            total += text_lead * 0.5
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

    # Content box heights (FIXED: increased for 6-piece sets)
    MAX_CONTENT_H_IN   = 3.10 if not data['has_gift_note'] else 2.75
    SIX_PC_CONTENT_IN  = 3.10 if not data['has_gift_note'] else 2.75
    THREE_PC_CONTENT_IN= 2.55 if not data['has_gift_note'] else 2.20
    FEW_CONTENT_IN     = 2.35 if not data['has_gift_note'] else 2.00

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
        # Add extra spacing between items - back to 50%
        if idx < len(items) - 1:  # Don't add extra space after last item
            ytxt -= text_lead * 0.5  # 50% spacing between items
        if overflow: break

    if overflow:
        remaining = len(items) - idx
        c.setFont("Helvetica-Oblique", 8)
        c.drawString(x, usable_bottom, f"[+{remaining} more…]")

# ─────────────────────────────────────────────────────────────────────────────
# SIMPLE MERGE FUNCTION (adapted from blanket orders)
# ─────────────────────────────────────────────────────────────────────────────
def merge_shipping_and_manufacturing_labels_simple(shipping_pdf_bytes, manufacturing_pdf_bytes, order_dataframe):
    """
    Simple positional merge: assumes shipping labels are in the same order as parsed data.
    Maps each shipping label to its corresponding manufacturing labels.
    """
    try:
        # Read PDFs
        shipping_pdf = PdfReader(shipping_pdf_bytes)
        manufacturing_pdf = PdfReader(manufacturing_pdf_bytes)
        
        # Extract order sequence from dataframe (preserves original order)
        seen_orders = []
        order_item_counts = []
        
        for order_id in order_dataframe['Order ID']:
            if order_id not in seen_orders:
                seen_orders.append(order_id)
                # Count how many items this order has
                item_count = len(order_dataframe[order_dataframe['Order ID'] == order_id])
                order_item_counts.append(item_count)
        
        # Build positional mapping: shipping label index → manufacturing label indices
        shipping_to_mfg = {}
        mfg_index = 0
        
        for shipping_index, item_count in enumerate(order_item_counts):
            # This shipping label gets the next 'item_count' manufacturing labels
            shipping_to_mfg[shipping_index] = list(range(mfg_index, mfg_index + item_count))
            mfg_index += item_count
        
        # Create merged PDF
        output_pdf = PdfWriter()
        total_shipping_labels = len(seen_orders)
        
        for ship_idx in range(total_shipping_labels):
            # Check if shipping label exists
            if ship_idx >= len(shipping_pdf.pages):
                break
            
            # Add shipping label
            output_pdf.add_page(shipping_pdf.pages[ship_idx])
            
            # Add all manufacturing labels for this order
            if ship_idx in shipping_to_mfg:
                for mfg_idx in shipping_to_mfg[ship_idx]:
                    if mfg_idx < len(manufacturing_pdf.pages):
                        output_pdf.add_page(manufacturing_pdf.pages[mfg_idx])
        
        # Write to buffer
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
            "🎁 Gift Notes","🔗 Merge Ship + MFG"
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
            st.subheader("📋 Manufacturing Plan - Production Summary")
            st.markdown("*6-pc sets count as 2 production units (2× 3-pc sets)*")
            df_mfg = df.copy()
            def units(r): return (int(r['Quantity']) * 2) if '6-pc' in r['Product Type'].lower() else int(r['Quantity'])
            df_mfg['Mfg_Units'] = df_mfg.apply(units, axis=1)

            c1, c2, c3, c4 = st.columns(4)
            with c1: st.metric("Total Orders", len(df['Order ID'].unique()))
            with c2: st.metric("Total Line Items", len(df))
            with c3: st.metric("Production Units", int(df_mfg['Mfg_Units'].sum()))
            with c4: st.metric("Gift Notes", int((df['Gift Message']=='YES').sum()))

            st.markdown("---")
            st.markdown("### 🧵 Thread Color Breakdown")
            th = df_mfg.groupby('Thread Color').agg({'Mfg_Units':'sum','Order ID':'count'}) \
                       .rename(columns={'Mfg_Units':'Sets to Embroider','Order ID':'Line Items'}) \
                       .sort_values('Sets to Embroider', ascending=False)
            th['Sets to Embroider'] = th['Sets to Embroider'].astype(int)
            cols = st.columns(min(len(th),4) or 1)
            for i,(t,rw) in enumerate(th.iterrows()):
                with cols[i % len(cols)]:
                    st.metric(f"🧵 {t}", f"{rw['Sets to Embroider']} sets", f"{rw['Line Items']} items")

            st.markdown("---")
            st.markdown("### 🎨 Towel Color Breakdown")
            col = df_mfg.groupby('Color').agg({'Mfg_Units':'sum','Order ID':'count'}) \
                        .rename(columns={'Mfg_Units':'Sets Needed','Order ID':'Line Items'}) \
                        .sort_values('Sets Needed', ascending=False)
            col['Sets Needed'] = col['Sets Needed'].astype(int)
            cols2 = st.columns(min(len(col),4) or 1)
            for i,(t,rw) in enumerate(col.iterrows()):
                with cols2[i % len(cols2)]:
                    st.metric(f"🎨 {t}", f"{rw['Sets Needed']} sets", f"{rw['Line Items']} items")

            st.markdown("---")
            st.markdown("### 📦 Product Type Breakdown")
            prod = df_mfg.groupby('Product Type').agg({'Quantity':'sum','Mfg_Units':'sum','Order ID':'count'}) \
                        .rename(columns={'Quantity':'Ordered Qty','Mfg_Units':'Production Units','Order ID':'Line Items'}) \
                        .sort_values('Production Units', ascending=False)
            prod['Ordered Qty'] = pd.to_numeric(prod['Ordered Qty'], errors='coerce').fillna(0).astype('int64')
            prod['Production Units'] = prod['Production Units'].astype(int)
            st.dataframe(prod, use_container_width=True)

            st.markdown("---")
            st.markdown("### 🎯 Color × Thread Matrix")
            matrix = df_mfg.groupby(['Color','Thread Color'])['Mfg_Units'].sum().unstack(fill_value=0).astype(int)
            matrix['TOTAL'] = matrix.sum(axis=1); matrix.loc['TOTAL'] = matrix.sum()
            st.dataframe(matrix, use_container_width=True)

        # ─────────────────────────────────────────────────────────────────────
        # TAB 3: Generate selected labels
        # ─────────────────────────────────────────────────────────────────────
        with tab3:
            st.subheader("Manufacturing Labels")
            selected = []
            for idx, row in df.iterrows():
                a,b = st.columns([0.1,0.9])
                with a:
                    if st.checkbox("", key=f"mfg_{idx}"):
                        selected.append(idx)
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
                if chosen and st.button("🎁 Generate Selected Gift Notes", type="primary"):
                    with st.spinner("Generating gift notes..."):
                        out = BytesIO(); c = canvas.Canvas(out, pagesize=landscape((4*inch,6*inch)))
                        for idx in chosen:
                            r = gifts.loc[idx]; o, it = r['_order_obj'], r['_item_obj']
                            generate_gift_note(c, o['order_id'], o['buyer_name'], it['gift_message'])
                            c.showPage()
                        c.save(); out.seek(0)
                        st.session_state['gift_notes_pdf'] = out.getvalue()
                        st.download_button("📥 Download Gift Notes PDF", out.getvalue(),
                                           "gift_notes.pdf","application/pdf")

        # ─────────────────────────────────────────────────────────────────────
        # TAB 5: SIMPLE MERGE (adapted from blanket orders)
        # ─────────────────────────────────────────────────────────────────────
        with tab5:
            st.subheader("🔗 Merge Shipping Labels with Manufacturing Labels")
            st.markdown(
                """
                **✨ Simple Merge Mode** (adapted from blanket orders)
                
                **How it works:**
                - Assumes shipping labels are in the **same order** as your packing slip PDF
                - One shipping label per order, even if the order has multiple items
                - Manufacturing labels are added after each shipping label
                
                **Requirements:**
                - Your shipping labels PDF must have labels in the same sequence as they appear in your packing slip
                - This is usually the case when you download/print shipping labels in order from Amazon
                
                **Steps:**
                1. Generate manufacturing labels in Tab 1 (or they'll be auto-generated)
                2. Upload your shipping labels PDF below
                3. Click "Merge Now"
                """
            )

            ship_pdf = st.file_uploader("📤 Upload Shipping Labels PDF", type=["pdf"], key="ship_pdf")
            auto_build = st.checkbox("Automatically generate manufacturing labels if missing", value=True)

            if st.button("🔗 Merge Now", type="primary"):
                if not ship_pdf:
                    st.error("Please upload the Shipping Labels PDF.")
                else:
                    # Ensure we have manufacturing labels PDF bytes
                    if not st.session_state['mfg_labels_pdf'] and auto_build:
                        with st.spinner("Generating manufacturing labels..."):
                            out = BytesIO()
                            c = canvas.Canvas(out, pagesize=landscape((4*inch,6*inch)))
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
                                generate_manufacturing_label(c, data)
                                c.showPage()
                            c.save()
                            out.seek(0)
                            st.session_state['mfg_labels_pdf'] = out.getvalue()

                    if not st.session_state['mfg_labels_pdf']:
                        st.error("Manufacturing labels PDF is missing. Generate them first in Table View.")
                    else:
                        with st.spinner("Merging PDFs using simple positional matching..."):
                            # Reset file pointer
                            ship_pdf.seek(0)
                            
                            # Use simple positional merge (same as blanket orders)
                            merged_buffer, num_shipping, num_mfg = merge_shipping_and_manufacturing_labels_simple(
                                ship_pdf,
                                BytesIO(st.session_state['mfg_labels_pdf']),
                                df
                            )
                            
                            if merged_buffer:
                                st.session_state['merged_pdf'] = merged_buffer.getvalue()
                                st.success(f"✅ Successfully merged {num_shipping} shipping labels with {num_mfg} manufacturing labels!")
                                
                                # Show multi-item orders
                                multi_item = df.groupby('Order ID').size()
                                multi_item = multi_item[multi_item > 1]
                                
                                if len(multi_item) > 0:
                                    with st.expander(f"ℹ️ Orders with multiple items ({len(multi_item)})"):
                                        for order_id, count in multi_item.items():
                                            buyer = df[df['Order ID'] == order_id]['Buyer'].iloc[0]
                                            st.write(f"• **{buyer}** ({order_id}): {count} items")
                                        st.info("📦 Each of these orders has ONE shipping label followed by MULTIPLE manufacturing labels")
                                
                                # Show orders with gift notes
                                gift_orders = df[df['Gift Message'] == 'YES']['Order ID'].unique()
                                if len(gift_orders) > 0:
                                    with st.expander(f"🎁 Orders with gift notes ({len(gift_orders)})"):
                                        for order_id in gift_orders:
                                            buyer = df[df['Order ID'] == order_id]['Buyer'].iloc[0]
                                            st.write(f"• **{buyer}** ({order_id})")
                                        st.success("These labels have a prominent RED BANNER at the top")
                                
                                # Show merge structure
                                with st.expander("📋 Merge Structure Preview"):
                                    st.markdown("**How labels are arranged:**")
                                    page_num = 1
                                    for idx, order_id in enumerate(df['Order ID'].drop_duplicates()):
                                        buyer = df[df['Order ID'] == order_id]['Buyer'].iloc[0]
                                        item_count = len(df[df['Order ID'] == order_id])
                                        has_gift = df[df['Order ID'] == order_id]['Gift Message'].iloc[0] == 'YES'
                                        gift_icon = " 🎁" if has_gift else ""
                                        
                                        st.markdown(f"**Page {page_num}:** Shipping label - {buyer}{gift_icon}")
                                        page_num += 1
                                        for i in range(item_count):
                                            st.markdown(f"**Page {page_num}:** Manufacturing label {i+1} - {buyer}{gift_icon}")
                                            page_num += 1
                                        st.markdown("---")
                                
                                st.download_button(
                                    "📥 Download Merged PDF",
                                    st.session_state['merged_pdf'],
                                    "merged_shipping_plus_manufacturing.pdf",
                                    "application/pdf",
                                    use_container_width=True
                                )

else:
    st.info("👆 Upload PDF files (packing slips) to get started")
