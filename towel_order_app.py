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
# PDF parser
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
                        ('Washcloth 1', r'First Washcloth:\s*(.+?)(?:\n|Second)'),
                        ('Washcloth 2', r'Second Washcloth:\s*(.+?)(?:\n|First Hand)'),
                        ('Hand Towel 1', r'First Hand Towel:\s*(.+?)(?:\n|Second Hand)'),
                        ('Hand Towel 2', r'Second Hand Towel:\s*(.+?)(?:\n|First Bath)'),
                        ('Bath Towel 1', r'First Bath Towel:\s*(.+?)(?:\n|Second Bath)'),
                        ('Bath Towel 2', r'Second Bath Towel:\s*(.+?)(?:\n|Item|Grand|Gift|Add|Choose|$)'),
                    ]
                elif 'Set-3Pcs' in sku:
                    product_type = '3-pc Set'
                    fields = [
                        ('Washcloth', r'Washcloth:\s*(.+?)(?:\n|Hand Towel)'),
                        ('Hand Towel', r'Hand Towel:\s*(.+?)(?:\n|Bath Towel)'),
                        ('Bath Towel', r'Bath Towel:\s*(.+?)(?:\n|Item|Grand|Gift|Add|$)'),
                    ]
                elif 'HT-2' in sku or 'HT-2PCS' in sku or 'HT-2Pcs' in sku:
                    product_type = '2-pc Hand Towel'
                    fields = [
                        ('Hand Towel 1', r'First Hand Towel:\s*(.+?)(?:\n|Second)'),
                        ('Hand Towel 2', r'Second Hand Towel:\s*(.+?)(?:\n|Item|Grand|$)'),
                    ]
                elif 'BT-2' in sku or 'BT-2Pcs' in sku:
                    product_type = '2-pc Bath Towel'
                    fields = [
                        ('Bath Towel 1', r'First Bath Towel:\s*(.+?)(?:\n|Second)'),
                        ('Bath Towel 2', r'Second Bath Towel:\s*(.+?)(?:\n|Item|Grand|$)'),
                    ]
                elif 'BS-1' in sku or 'BS-1Pcs' in sku:
                    product_type = 'Bath Sheet (Oversized)'
                    fields = [('Bath Sheet', r'Oversized Bath Sheet:\s*(.+?)(?:\n|Item|Grand|$)')]

                if fields:
                    for lbl, pat in fields:
                        m = re.search(pat, content)
                        if m: custom.append((lbl, m.group(1).strip()))

                gift = ''
                m = re.search(r'Gift Message:\s*(.+?)(?:\n|Item|Grand|$)', content)
                if m: gift = m.group(1).strip()
                else:
                    m = re.search(r'Add Gift Card:\s*(.+?)(?:\n|Item|Grand|$)', content)
                    if m: gift = m.group(1).strip()

                current['items'].append({
                    'sku': sku, 'product_type': product_type, 'towel_color': towel_color,
                    'quantity': quantity, 'font': font, 'font_color': font_color,
                    'customizations': custom, 'gift_message': gift
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
    for _, value in items:
        lines = simpleSplit(value, "Helvetica-BoldOblique", text_fs, width_pts)
        total += label_lead + max(1, len(lines)) * text_lead
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
# Gift note label (kept for completeness)
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
# Manufacturing label renderer (6-pc box height = 2.95")
# ─────────────────────────────────────────────────────────────────────────────
def generate_manufacturing_label(c, data):
    W, H = landscape((4 * inch, 6 * inch))
    left, right = 0.25 * inch, (6 * inch) - 0.25 * inch
    y = (4 * inch) - 0.25 * inch

    # Header
    c.setFont("Helvetica-Bold", 13); c.setFillColor(colors.black)
    c.drawString(left, y, data['buyer'])
    if data['has_gift_note']:
        c.setFont("Helvetica-Bold", 11); c.setFillColor(colors.HexColor('#D32F2F'))
        c.drawString(left + c.stringWidth(data['buyer'], "Helvetica-Bold", 13) + 0.2*inch, y, "GIFT")
        c.setFillColor(colors.black)
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

    # Content box heights
    MAX_CONTENT_H_IN   = 3.05
    SIX_PC_CONTENT_IN  = 2.95   # ← per your request
    THREE_PC_CONTENT_IN= 2.55
    FEW_CONTENT_IN     = 2.35

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

    # LEFT column (product specs)
    col_y = content_top - 0.12*inch
    col_c = left + left_w/2
    c.setFont("Helvetica", 8); c.drawCentredString(col_c, col_y, "PRODUCT:"); col_y -= 0.22*inch
    c.setFont("Helvetica-Bold", 13); c.drawCentredString(col_c, col_y, data['product_type'].upper()); col_y -= 0.26*inch
    c.setFont("Helvetica-Bold", 16); c.drawCentredString(col_c, col_y, data['towel_color'].upper()); col_y -= 0.24*inch
    c.setFont("Helvetica-BoldOblique" if int(data['quantity'])>2 else "Helvetica-Bold", 18)
    c.drawCentredString(col_c, col_y, f"QTY: {data['quantity']}"); col_y -= 0.34*inch
    c.setLineWidth(0.5); c.line(left + 0.05*inch, col_y, left_right - 0.05*inch, col_y); col_y -= 0.24*inch
    c.setFont("Helvetica", 8); c.drawCentredString(col_c, col_y, "THREAD COLOR:"); col_y -= 0.2*inch
    c.setFont("Helvetica-Bold", 15); c.drawCentredString(col_c, col_y, data['thread_color'].upper()); col_y -= 0.14*inch
    c.setFont("Helvetica", 10); c.drawCentredString(col_c, col_y, get_spanish_color(data['thread_color']))

    # RIGHT column header
    right_header_y = content_top - 0.12*inch
    c.setFont("Helvetica-Bold", 9)
    c.drawString(right_left + 0.05*inch, right_header_y, "PERSONALIZATION:")

    # Usable area (within the fixed box, with padding)
    pad_t, pad_b, pad_r, pad_l = 0.10*inch, 0.10*inch, 0.10*inch, 0.08*inch
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
        if overflow: break

    if overflow:
        remaining = len(items) - idx
        c.setFont("Helvetica-Oblique", 8)
        c.drawString(x, usable_bottom, f"[+{remaining} more…]")

    # Gift strip
    y_after_box = content_bottom - 0.15*inch
    if data['has_gift_note']:
        h = 0.25*inch
        c.setLineWidth(2); c.rect(left, y_after_box - h, right-left, h, stroke=1, fill=0)
        c.setFont("Helvetica-Bold", 10); c.drawString(left + 0.1*inch, y_after_box - 0.16*inch, "🎁 GIFT NOTE: YES")

# ─────────────────────────────────────────────────────────────────────────────
# Helpers for MERGE
# ─────────────────────────────────────────────────────────────────────────────
ORDER_ID_RE = re.compile(r"\b\d{3}-\d{7}-\d{7}\b")

def index_mfg_pdf_by_order(pdf_bytes):
    """
    Returns dict[order_id] -> list(page_index) by OCRing text from the
    manufacturing labels PDF (each page contains 'Order: <id>').
    """
    mapping = {}
    with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
        for i, page in enumerate(pdf.pages):
            txt = page.extract_text() or ""
            m = re.search(r"Order:\s*(\d{3}-\d{7}-\d{7})", txt)
            if m:
                oid = m.group(1).strip()
                mapping.setdefault(oid, []).append(i)
    return mapping

def extract_shipping_key_from_page(page):
    """
    Try to find Order ID on a shipping label page; if not present,
    extract recipient name after 'SHIP TO:' marker.
    """
    txt = page.extract_text() or ""
    
    # 1) Prefer explicit Order ID if present
    m = ORDER_ID_RE.search(txt)
    if m:
        return ("order_id", m.group(0))

    # 2) Fallback to recipient name - look for text after "SHIP TO:"
    lines = txt.splitlines()
    
    # Find the "SHIP TO:" line
    ship_to_index = -1
    for i, line in enumerate(lines):
        if "SHIP TO" in line.upper():
            ship_to_index = i
            break
    
    # If found, get the next non-empty line as the name
    if ship_to_index >= 0:
        for i in range(ship_to_index + 1, min(ship_to_index + 4, len(lines))):
            candidate = lines[i].strip()
            # Look for a line with mostly letters and spaces (likely a name)
            if candidate and len(candidate) > 3 and re.search(r'[A-Za-z]{3,}', candidate):
                # Skip lines that are clearly addresses (have numbers/street indicators)
                if not re.search(r'^\d+\s|ST\s|AVE\s|DR\s|BLVD\s|ROAD\s|LN\s|APT\s|UNIT\s', candidate, re.IGNORECASE):
                    return ("buyer_name", candidate.strip())
    
    # 3) Last resort: try first alphabetic-heavy line
    for line in lines[:10]:
        line = line.strip()
        if line and len(line) > 3 and re.search(r'[A-Za-z]{3,}', line):
            if not re.search(r'^\d+\s|FAIRFIELD|GLORIA|JERSEY|SHIP|TRACKING|BILLING|UPS|USPS', line, re.IGNORECASE):
                return ("buyer_name", line.strip())
    
    return ("unknown", "")

def normalize_name(s):
    """Normalize name for fuzzy matching - lowercase, single spaces"""
    return re.sub(r"\s+", " ", (s or "").strip()).lower()

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
                            'has_gift_note': bool(it['gift_message']),
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
                    st.write(f"**{row['Order ID']}** — {row['Product Type']} — {row['Color']} — Qty: {row['Quantity']}")
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
                                'has_gift_note': bool(it['gift_message']),
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
        # TAB 5: MERGE Shipping Labels + Manufacturing Labels (FIXED)
        # ─────────────────────────────────────────────────────────────────────
        with tab5:
            st.subheader("🔗 Merge Shipping Labels with Manufacturing Labels")
            st.markdown(
                "- Upload your **Shipping Labels PDF** (one label per page).\n"
                "- Click **Merge**. The app pairs each shipping page with the matching **Order ID**; "
                "if no Order ID is visible on the label page, it falls back to the **recipient name**."
            )

            ship_pdf = st.file_uploader("Upload Shipping Labels PDF", type=["pdf"], key="ship_pdf")

            # If the user hasn't generated manufacturing labels yet, we can build them on-demand
            auto_build = st.checkbox("Automatically generate manufacturing labels if missing", value=True)

            if st.button("🔗 Merge Now", type="primary"):
                if not ship_pdf:
                    st.error("Please upload the Shipping Labels PDF.")
                else:
                    # Ensure we have manufacturing labels PDF bytes
                    if not st.session_state['mfg_labels_pdf'] and auto_build:
                        with st.spinner("Generating manufacturing labels..."):
                            out = BytesIO(); c = canvas.Canvas(out, pagesize=landscape((4*inch,6*inch)))
                            for _, r in df.iterrows():
                                o, it = r['_order_obj'], r['_item_obj']
                                data = {
                                    'order_id': o['order_id'], 'buyer': o['buyer_name'], 'date': o['order_date'],
                                    'shipping': o['shipping_service'], 'quantity': it['quantity'],
                                    'product_type': it['product_type'], 'towel_color': it['towel_color'],
                                    'thread_color': it['font_color'], 'font': it['font'],
                                    'customizations': it['customizations'],
                                    'has_gift_note': bool(it['gift_message']),
                                    'item_number': r['item_number'], 'item_count': r['item_count']
                                }
                                generate_manufacturing_label(c, data); c.showPage()
                            c.save(); out.seek(0)
                            st.session_state['mfg_labels_pdf'] = out.getvalue()

                    if not st.session_state['mfg_labels_pdf']:
                        st.error("Manufacturing labels PDF is missing. Generate them first in Table View.")
                    else:
                        with st.spinner("Merging PDFs by order..."):
                            # Index manufacturing pages by Order ID
                            mfg_index = index_mfg_pdf_by_order(st.session_state['mfg_labels_pdf'])
                            
                            # Prepare Buyer → Order IDs mapping from df
                            buyer_to_oids = (
                                df.groupby('Buyer')['Order ID']
                                  .apply(list)
                                  .to_dict()
                            )
                            # Normalize buyer keys for fuzzy match
                            buyer_to_oids_norm = {normalize_name(k): v for k, v in buyer_to_oids.items()}

                            # Read shipping labels with PyPDF2
                            ship_reader = PdfReader(ship_pdf)
                            mfg_reader = PdfReader(BytesIO(st.session_state['mfg_labels_pdf']))
                            writer = PdfWriter()

                            # IMPORTANT: Reset file pointer before using pdfplumber
                            ship_pdf.seek(0)
                            
                            # Open with pdfplumber ONCE, outside the loop
                            with pdfplumber.open(ship_pdf) as pdf_ship:
                                unmatched_pages = 0
                                
                                for i, page in enumerate(ship_reader.pages):
                                    # Always add the shipping label page first
                                    writer.add_page(page)

                                    # Extract text from the corresponding pdfplumber page
                                    page_txt = pdf_ship.pages[i].extract_text() or ""
                                    
                                    # Try order ID first
                                    m = ORDER_ID_RE.search(page_txt)
                                    added = False
                                    
                                    if m:
                                        oid = m.group(0)
                                        for pidx in mfg_index.get(oid, []):
                                            writer.add_page(mfg_reader.pages[pidx])
                                            added = True
                                    else:
                                        # Fallback to buyer name
                                        key_type, buyer_guess = extract_shipping_key_from_page(pdf_ship.pages[i])
                                        if key_type == "buyer_name":
                                            oids = buyer_to_oids_norm.get(normalize_name(buyer_guess), [])
                                            for oid in oids:
                                                for pidx in mfg_index.get(oid, []):
                                                    writer.add_page(mfg_reader.pages[pidx])
                                                    added = True

                                    if not added:
                                        unmatched_pages += 1

                            merged_out = BytesIO()
                            writer.write(merged_out)
                            merged_out.seek(0)
                            st.session_state['merged_pdf'] = merged_out.getvalue()

                        st.success("✅ Merged shipping labels with manufacturing labels")
                        if unmatched_pages:
                            st.info(f"ℹ️ {unmatched_pages} shipping page(s) had no match (no Order ID on label and buyer name didn't match).")
                        st.download_button(
                            "📥 Download Merged PDF",
                            st.session_state['merged_pdf'],
                            "merged_shipping_plus_manufacturing.pdf",
                            "application/pdf",
                            use_container_width=True
                        )

else:
    st.info("👆 Upload PDF files (packing slips) to get started")
