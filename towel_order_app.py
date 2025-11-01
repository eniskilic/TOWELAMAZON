import streamlit as st
import pdfplumber
import re
import pandas as pd
from io import BytesIO
from reportlab.lib.pagesizes import landscape, inch
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.utils import simpleSplit

# Page config
st.set_page_config(page_title="Towel Order Parser", layout="wide", page_icon="🧺")

# Initialize session state
if 'mfg_labels_pdf' not in st.session_state:
    st.session_state['mfg_labels_pdf'] = None
if 'gift_notes_pdf' not in st.session_state:
    st.session_state['gift_notes_pdf'] = None

# Color translations (English to Spanish)
COLOR_TRANSLATIONS = {
    'WHITE': 'Blanco', 'BLACK': 'Negro', 'NAVY': 'Azul Marino', 'NAVY BLUE': 'Azul Marino',
    'GOLD': 'Oro', 'SILVER': 'Plata', 'RED': 'Rojo', 'BLUE': 'Azul', 'MID BLUE': 'Azul Medio',
    'LIGHT BLUE': 'Azul Claro', 'DARK BLUE': 'Azul Oscuro', 'GREEN': 'Verde',
    'LIGHT GREEN': 'Verde Claro', 'DARK GREEN': 'Verde Oscuro', 'GREY': 'Gris', 'GRAY': 'Gris',
    'LIGHT GREY': 'Gris Claro', 'LIGHT GRAY': 'Gris Claro', 'DARK GREY': 'Gris Oscuro',
    'DARK GRAY': 'Gris Oscuro', 'BROWN': 'Marrón', 'PINK': 'Rosa', 'LIGHT PINK': 'Rosa Claro',
    'HOT PINK': 'Rosa Fuerte', 'PURPLE': 'Morado', 'YELLOW': 'Amarillo', 'ORANGE': 'Naranja',
    'CREAM': 'Crema', 'BEIGE': 'Beige', 'TAN': 'Bronceado', 'BURGUNDY': 'Burdeos', 'MAROON': 'Granate'
}

def get_spanish_color(english_color):
    color_upper = english_color.upper().strip()
    return COLOR_TRANSLATIONS.get(color_upper, english_color)

# ---------------- PDF PARSER ----------------
def parse_towel_orders(pdf_file):
    orders = []
    with pdfplumber.open(pdf_file) as pdf:
        current_order = None
        for page in pdf.pages:
            text = page.extract_text() or ""

            if 'Order ID:' in text:
                if current_order and current_order['items']:
                    orders.append(current_order)
                order_id_match = re.search(r'Order ID:\s*([\d-]+)', text)
                current_order = {
                    'order_id': order_id_match.group(1).strip() if order_id_match else '',
                    'order_date': '',
                    'buyer_name': '',
                    'shipping_service': '',
                    'items': []
                }
                date_match = re.search(r'Order Date:\s*(.+?)(?:\n|Shipping)', text)
                if date_match:
                    current_order['order_date'] = date_match.group(1).strip()
                shipping_match = re.search(r'Shipping Service:\s*(.+?)(?:\n|Buyer)', text)
                if shipping_match:
                    current_order['shipping_service'] = shipping_match.group(1).strip()
                ship_to_match = re.search(r'Ship To:\s*\n\s*(.+?)(?:\n)', text)
                if ship_to_match:
                    current_order['buyer_name'] = ship_to_match.group(1).strip()

            if current_order:
                sections = re.split(r'(SKU:\s*[^\n]+)', text)
                for i in range(1, len(sections), 2):
                    if i + 1 >= len(sections):
                        continue
                    sku_line = sections[i]
                    content = sections[i + 1]

                    sku_match = re.search(r'SKU:\s*([^\n]+)', sku_line)
                    if not sku_match:
                        continue
                    sku = sku_match.group(1).strip()
                    sku = re.split(r'\s+(?:Item|Tax|total|\$|Promotion)', sku)[0].strip()

                    qty_match = re.search(r'Quantity[^\d]*(\d+)', text[:text.find(sku_line)])
                    quantity = qty_match.group(1) if qty_match else '1'

                    font_match = re.search(r'Choose Your Font:\s*(.+?)(?:\n|Font Color)', content)
                    font = font_match.group(1).strip() if font_match else ''

                    color_match = re.search(r'Font Color:\s*([^(#\n]+)', content)
                    font_color = color_match.group(1).strip() if color_match else ''

                    sku_parts = sku.split('-')
                    towel_color = sku_parts[-1].strip() if len(sku_parts) >= 2 else 'Unknown'
                    towel_color = re.split(r'\s+(?:Tax|Item|total|Promotion|\$)', towel_color)[0].strip()
                    towel_color = re.sub(r'[\(\)\[\]]', '', towel_color).strip()

                    customizations = []
                    if 'Set-6Pcs' in sku:
                        product_type = '6-pc Set'
                        fields = [
                            ('Washcloth 1', r'First Washcloth:\s*(.+?)(?:\n|Second)'),
                            ('Washcloth 2', r'Second Washcloth:\s*(.+?)(?:\n|First Hand)'),
                            ('Hand Towel 1', r'First Hand Towel:\s*(.+?)(?:\n|Second Hand)'),
                            ('Hand Towel 2', r'Second Hand Towel:\s*(.+?)(?:\n|First Bath)'),
                            ('Bath Towel 1', r'First Bath Towel:\s*(.+?)(?:\n|Second Bath)'),
                            ('Bath Towel 2', r'Second Bath Towel:\s*(.+?)(?:\n|Item|Grand|Gift|Add|Choose|$)')
                        ]
                    elif 'Set-3Pcs' in sku:
                        product_type = '3-pc Set'
                        fields = [
                            ('Washcloth', r'Washcloth:\s*(.+?)(?:\n|Hand Towel)'),
                            ('Hand Towel', r'Hand Towel:\s*(.+?)(?:\n|Bath Towel)'),
                            ('Bath Towel', r'Bath Towel:\s*(.+?)(?:\n|Item|Grand|Gift|Add|$)')
                        ]
                    elif 'HT-2' in sku or 'HT-2PCS' in sku or 'HT-2Pcs' in sku:
                        product_type = '2-pc Hand Towel'
                        fields = [
                            ('Hand Towel 1', r'First Hand Towel:\s*(.+?)(?:\n|Second)'),
                            ('Hand Towel 2', r'Second Hand Towel:\s*(.+?)(?:\n|Item|Grand|$)')
                        ]
                    elif 'BT-2' in sku or 'BT-2Pcs' in sku:
                        product_type = '2-pc Bath Towel'
                        fields = [
                            ('Bath Towel 1', r'First Bath Towel:\s*(.+?)(?:\n|Second)'),
                            ('Bath Towel 2', r'Second Bath Towel:\s*(.+?)(?:\n|Item|Grand|$)')
                        ]
                    elif 'BS-1' in sku or 'BS-1Pcs' in sku:
                        product_type = 'Bath Sheet (Oversized)'
                        fields = [('Bath Sheet', r'Oversized Bath Sheet:\s*(.+?)(?:\n|Item|Grand|$)')]
                    else:
                        product_type, fields = 'Unknown', None

                    if fields:
                        for label, pattern in fields:
                            m = re.search(pattern, content)
                            if m:
                                customizations.append((label, m.group(1).strip()))

                    gift_message = ''
                    gift_msg_match = re.search(r'Gift Message:\s*(.+?)(?:\n|Item|Grand|$)', content)
                    if gift_msg_match:
                        gift_message = gift_msg_match.group(1).strip()
                    else:
                        gift_card_match = re.search(r'Add Gift Card:\s*(.+?)(?:\n|Item|Grand|$)', content)
                        if gift_card_match:
                            gift_message = gift_card_match.group(1).strip()

                    current_order['items'].append({
                        'sku': sku, 'product_type': product_type, 'towel_color': towel_color,
                        'quantity': quantity, 'font': font, 'font_color': font_color,
                        'customizations': customizations, 'gift_message': gift_message
                    })

        if current_order and current_order['items']:
            orders.append(current_order)
    return orders

# ---------------- LAYOUT HELPERS ----------------
def compute_wrapped_heights(items, label_fs, text_fs, width_px):
    """Return total height in points required to render all (label,text) pairs with wrapping."""
    # Leading (line spacing) ~ 1.15x of size for labels, 1.25x for text
    label_lead = label_fs * 1.15
    text_lead = text_fs * 1.25
    total = 0
    for (label, text) in items:
        # labels never wrap; values wrap
        lines = simpleSplit(text, "Helvetica-BoldOblique", text_fs, width_px)
        total += label_lead + len(lines) * text_lead
    return total, label_lead, text_lead

def fit_fonts_to_height(items, max_width_pts, avail_height_pts,
                        label_fs_start=11, text_fs_start=15, min_fs=8):
    """
    Iteratively shrink fonts until the wrapped content fits into the available height.
    Returns label_fs, text_fs, label_lead, text_lead.
    """
    label_fs = float(label_fs_start)
    text_fs = float(text_fs_start)

    for _ in range(18):  # tight loop with a safe cap
        total, label_lead, text_lead = compute_wrapped_heights(items, label_fs, text_fs, max_width_pts)
        if total <= avail_height_pts:
            return label_fs, text_fs, label_lead, text_lead
        # scale down both, but keep text slightly larger than label for readability
        scale = max(0.85, avail_height_pts / max(total, 1))
        label_fs = max(min_fs, label_fs * scale)
        text_fs  = max(min_fs,  text_fs  * scale)
        if label_fs == min_fs and text_fs == min_fs:
            # still overflowing? we'll truncate the last item with a continuation marker during draw
            return label_fs, text_fs, label_lead, text_lead
    return label_fs, text_fs, label_lead, text_lead

# ---------------- LABEL RENDERER ----------------
def generate_manufacturing_label(c, data, is_first=True):
    W, H = landscape((4 * inch, 6 * inch))
    left = 0.25 * inch
    right = W - 0.25 * inch
    y = H - 0.25 * inch

    # HEADER
    c.setFont("Helvetica-Bold", 13)
    c.setFillColor(colors.black)
    c.drawString(left, y, data['buyer'])
    if data['has_gift_note']:
        c.setFont("Helvetica-Bold", 11)
        c.setFillColor(colors.HexColor('#D32F2F'))
        c.drawString(left + c.stringWidth(data['buyer'], "Helvetica-Bold", 13) + 0.2 * inch, y, "GIFT")
        c.setFillColor(colors.black)
    if data['item_count'] > 1:
        c.setFont("Helvetica-Bold", 11)
        c.drawRightString(right, y, f"▲ [{data['item_number']} of {data['item_count']}]")

    y -= 0.16 * inch
    c.setFont("Helvetica", 11)
    c.drawString(left, y, f"Order: {data['order_id']}")
    c.setFont("Helvetica", 9)
    c.drawRightString(right, y, data['shipping'])
    y -= 0.15 * inch
    c.setFont("Helvetica", 9)
    c.drawString(left, y, data['date'])
    y -= 0.22 * inch
    c.setLineWidth(2)
    c.line(left, y, right, y)
    y -= 0.15 * inch

    # TWO COLUMNS
    total_width = right - left
    left_col_w  = total_width * 0.40
    right_col_w = total_width * 0.60
    left_col_right  = left + left_col_w
    right_col_left  = left_col_right + 0.08 * inch

    # Content height (taller when many customizations)
    num_customizations = len(data['customizations'])
    content_height = 2.5 * inch if num_customizations <= 3 else 2.9 * inch
    if num_customizations >= 6:
        content_height = 3.5 * inch  # plenty of room for 6-pc sets

    content_top = y
    content_bottom = y - content_height
    c.setLineWidth(2)
    c.rect(left, content_bottom, right - left, content_height, stroke=1, fill=0)
    c.setLineWidth(1.5)
    c.line(left_col_right + 0.04 * inch, content_top, left_col_right + 0.04 * inch, content_bottom)

    # LEFT COLUMN
    col_y = content_top - 0.12 * inch
    col_center = left + (left_col_w / 2)
    c.setFont("Helvetica", 8);  c.drawCentredString(col_center, col_y, "PRODUCT:"); col_y -= 0.22 * inch
    c.setFont("Helvetica-Bold", 13); c.drawCentredString(col_center, col_y, data['product_type'].upper()); col_y -= 0.26 * inch
    c.setFont("Helvetica-Bold", 16); c.drawCentredString(col_center, col_y, data['towel_color'].upper()); col_y -= 0.24 * inch
    qty_value = int(data['quantity'])
    c.setFont("Helvetica-BoldOblique" if qty_value > 2 else "Helvetica-Bold", 18)
    c.drawCentredString(col_center, col_y, f"QTY: {data['quantity']}"); col_y -= 0.36 * inch
    c.setLineWidth(0.5); c.line(left + 0.05 * inch, col_y, left_col_right - 0.05 * inch, col_y); col_y -= 0.24 * inch
    c.setFont("Helvetica", 8); c.drawCentredString(col_center, col_y, "THREAD COLOR:"); col_y -= 0.2 * inch
    c.setFont("Helvetica-Bold", 15); c.drawCentredString(col_center, col_y, data['thread_color'].upper()); col_y -= 0.14 * inch
    c.setFont("Helvetica", 10); c.drawCentredString(col_center, col_y, get_spanish_color(data['thread_color']))

    # RIGHT COLUMN HEADER
    right_header_y = content_top - 0.12 * inch
    c.setFont("Helvetica-Bold", 9)
    c.drawString(right_col_left + 0.05 * inch, right_header_y, "PERSONALIZATION:")

    # Usable area inside right column (points)
    top_pad = 0.10 * inch
    bottom_pad = 0.10 * inch
    usable_top = right_header_y - top_pad
    usable_bottom = content_bottom + bottom_pad
    usable_height_pts = max(1, usable_top - usable_bottom)
    usable_width_pts = right - (right_col_left + 0.08 * inch) - 0.12 * inch  # right padding

    items = data['customizations']

    # Fit fonts to height considering wrapping
    # Start larger for small lists, smaller for 6 lines
    start_label = 12 if len(items) <= 3 else 11
    start_text  = 16 if len(items) <= 3 else 15
    if len(items) >= 6:
        start_label, start_text = 10, 14

    label_fs, text_fs, label_lead, text_lead = fit_fonts_to_height(
        items, usable_width_pts, usable_height_pts,
        label_fs_start=start_label, text_fs_start=start_text, min_fs=8
    )

    # DRAW personalization with safe wrapping and strict line-by-line advance
    x_text = right_col_left + 0.08 * inch
    y_text = usable_top
    overflow = False

    for idx, (label, value) in enumerate(items):
        # If next label line would go below bottom, stop and mark overflow
        if y_text - label_lead < usable_bottom:
            overflow = True
            break
        c.setFont("Helvetica", label_fs)
        c.drawString(x_text, y_text, f"{label}:")
        y_text -= label_lead

        # Wrap value to available width
        wrapped = simpleSplit(value, "Helvetica-BoldOblique", text_fs, usable_width_pts)
        for line in wrapped:
            if y_text - text_lead < usable_bottom:
                overflow = True
                break
            c.setFont("Helvetica-BoldOblique", text_fs)
            c.drawString(x_text, y_text, line)
            y_text -= text_lead
        if overflow:
            break

    # If overflow, add continuation marker at the bottom edge
    if overflow:
        remaining = len(items) - idx
        c.setFont("Helvetica-Oblique", 8)
        c.drawString(x_text, usable_bottom, f"[+{remaining} more…]")

    # GIFT FLAG BOX
    y_bottom = content_bottom - 0.15 * inch
    if data['has_gift_note']:
        h = 0.25 * inch
        c.setLineWidth(2)
        c.rect(left, y_bottom - h, right - left, h, stroke=1, fill=0)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(left + 0.1 * inch, y_bottom - 0.16 * inch, "🎁 GIFT NOTE: YES")

# ---------------- GIFT NOTE LABEL ----------------
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
    max_width = W - 2*margin - 0.8*inch
    lines = simpleSplit(gift_message, "Helvetica-Oblique", 14, max_width)
    for line in lines:
        c.drawCentredString(W / 2, y, line); y -= 0.22 * inch
    c.setFont("Helvetica-Bold", 12); c.setFillColor(colors.HexColor('#8B4513'))
    c.drawCentredString(W / 2, margin + 0.6*inch, f"To: {buyer_name}")
    c.setFont("Helvetica", 7); c.setFillColor(colors.grey)
    c.drawRightString(W - margin - 0.15*inch, margin + 0.2*inch, f"Order: {order_id}")

# ---------------- STREAMLIT APP ----------------
st.title("🧺 Towel Order Parser & Label Generator")
st.markdown("**Upload Amazon packing slip PDFs to generate manufacturing labels**")

uploaded_files = st.file_uploader(
    "Upload PDF files", type=['pdf'], accept_multiple_files=True,
    help="Upload one or more Amazon packing slip PDFs"
)

if uploaded_files:
    st.session_state['mfg_labels_pdf'] = None
    st.session_state['gift_notes_pdf'] = None

    all_orders = []
    with st.spinner("Parsing PDFs..."):
        for uploaded_file in uploaded_files:
            try:
                orders = parse_towel_orders(uploaded_file)
                all_orders.extend(orders)
            except Exception as e:
                st.error(f"Error parsing {uploaded_file.name}: {e}")

    if all_orders:
        rows = []
        for order in all_orders:
            for item in order['items']:
                rows.append({
                    'Order ID': order['order_id'],
                    'Date': order['order_date'],
                    'Buyer': order['buyer_name'],
                    'Shipping': order['shipping_service'],
                    'Product Type': item['product_type'],
                    'Color': item['towel_color'],
                    'Quantity': item['quantity'],
                    'Font': item['font'],
                    'Thread Color': item['font_color'],
                    'Customizations': ' | '.join([f"{l}: {t}" for l, t in item['customizations']]),
                    'Gift Message': 'YES' if item['gift_message'] else 'NO',
                    '_order_obj': order, '_item_obj': item
                })
        df = pd.DataFrame(rows)
        df.index = range(1, len(df) + 1)
        df['item_count'] = df.groupby('Order ID')['Order ID'].transform('count')
        df['item_number'] = df.groupby('Order ID').cumcount() + 1

        st.success(f"✅ Parsed {len(all_orders)} orders with {len(df)} items")

        tab1, tab2, tab3, tab4 = st.tabs(
            ["📊 Table View", "📋 Manufacturing Plan", "🏷️ Manufacturing Labels", "🎁 Gift Notes"]
        )

        with tab1:
            st.subheader("Order Data")
            display_df = df.drop(columns=['_order_obj', '_item_obj'])
            st.dataframe(display_df, use_container_width=True, height=420)

            col1, col2 = st.columns(2)
            with col1:
                gen_all = st.button("🏷️ Generate ALL Manufacturing Labels", type="primary", use_container_width=True)
            with col2:
                dl_placeholder = st.empty()

            if gen_all:
                with st.spinner("Generating all manufacturing labels..."):
                    output = BytesIO()
                    c = canvas.Canvas(output, pagesize=landscape((4 * inch, 6 * inch)))
                    for _, row in df.iterrows():
                        o = row['_order_obj']; it = row['_item_obj']
                        label_data = {
                            'order_id': o['order_id'], 'buyer': o['buyer_name'],
                            'date': o['order_date'], 'shipping': o['shipping_service'],
                            'quantity': it['quantity'], 'product_type': it['product_type'],
                            'towel_color': it['towel_color'], 'thread_color': it['font_color'],
                            'font': it['font'], 'customizations': it['customizations'],
                            'has_gift_note': bool(it['gift_message']),
                            'item_number': row['item_number'], 'item_count': row['item_count']
                        }
                        generate_manufacturing_label(c, label_data); c.showPage()
                    c.save(); output.seek(0)
                    st.session_state['mfg_labels_pdf'] = output.getvalue()
                    st.success(f"✅ Generated {len(df)} manufacturing labels")
                    with dl_placeholder:
                        st.download_button("📥 Download PDF", st.session_state['mfg_labels_pdf'],
                                           "all_manufacturing_labels.pdf", "application/pdf",
                                           use_container_width=True, key="dl_all_mfg")
            elif st.session_state.get('mfg_labels_pdf'):
                with dl_placeholder:
                    st.download_button("📥 Download PDF", st.session_state['mfg_labels_pdf'],
                                       "all_manufacturing_labels.pdf", "application/pdf",
                                       use_container_width=True, key="dl_all_existing")

            col1, col2 = st.columns(2)
            with col1:
                csv = display_df.to_csv(index=True).encode('utf-8')
                st.download_button("📥 Export to CSV", csv, "towel_orders.csv", "text/csv", use_container_width=True)
            with col2:
                buffer = BytesIO()
                with pd.ExcelWriter(buffer, engine='xlsxwriter') as w:
                    display_df.to_excel(w, index=True, sheet_name='Orders')
                st.download_button("📥 Export to Excel", buffer.getvalue(),
                                   "towel_orders.xlsx", "application/vnd.ms-excel",
                                   use_container_width=True)

            st.markdown("---")

            gift_items_count = int((df['Gift Message'] == 'YES').sum())
            if gift_items_count:
                c1, c2 = st.columns(2)
                with c1:
                    gen_gifts = st.button(f"🎁 Generate ALL Gift Notes ({gift_items_count} items)",
                                          type="secondary", use_container_width=True)
                with c2:
                    gift_dl_ph = st.empty()

                if gen_gifts:
                    with st.spinner("Generating all gift notes..."):
                        output = BytesIO()
                        c = canvas.Canvas(output, pagesize=landscape((4 * inch, 6 * inch)))
                        count = 0
                        for _, row in df.iterrows():
                            if row['Gift Message'] == 'YES':
                                o = row['_order_obj']; it = row['_item_obj']
                                generate_gift_note(c, o['order_id'], o['buyer_name'], it['gift_message'])
                                c.showPage(); count += 1
                        c.save(); output.seek(0)
                        st.session_state['gift_notes_pdf'] = output.getvalue()
                        st.success(f"✅ Generated {count} gift notes")
                        with gift_dl_ph:
                            st.download_button("📥 Download PDF", st.session_state['gift_notes_pdf'],
                                               "all_gift_notes.pdf", "application/pdf",
                                               use_container_width=True, key="dl_gifts")
                elif st.session_state.get('gift_notes_pdf'):
                    with gift_dl_ph:
                        st.download_button("📥 Download PDF", st.session_state['gift_notes_pdf'],
                                           "all_gift_notes.pdf", "application/pdf",
                                           use_container_width=True, key="dl_gifts_existing")
            else:
                st.info("ℹ️ No gift messages in current orders")

        with tab2:
            st.subheader("📋 Manufacturing Plan - Production Summary")
            st.markdown("*6-pc sets count as 2 production units (2× 3-pc sets)*")

            df_mfg = df.copy()
            def calc_units(r):
                q = int(r['Quantity'])
                return q * 2 if '6-pc' in r['Product Type'].lower() else q
            df_mfg['Mfg_Units'] = df_mfg.apply(calc_units, axis=1)

            c1, c2, c3, c4 = st.columns(4)
            with c1: st.metric("Total Orders", len(df['Order ID'].unique()))
            with c2: st.metric("Total Line Items", len(df))
            with c3: st.metric("Production Units", int(df_mfg['Mfg_Units'].sum()))
            with c4: st.metric("Gift Notes", int((df['Gift Message'] == 'YES').sum()))
            st.markdown("---")

            st.markdown("### 🧵 Thread Color Breakdown")
            th = df_mfg.groupby('Thread Color').agg({'Mfg_Units':'sum', 'Order ID':'count'}) \
                       .rename(columns={'Mfg_Units':'Sets to Embroider','Order ID':'Line Items'}) \
                       .sort_values('Sets to Embroider', ascending=False)
            th['Sets to Embroider'] = th['Sets to Embroider'].astype(int)
            cols = st.columns(min(len(th), 4) or 1)
            for i, (t, r) in enumerate(th.iterrows()):
                with cols[i % len(cols)]:
                    st.metric(f"🧵 {t}", f"{r['Sets to Embroider']} sets", f"{r['Line Items']} items")

            st.markdown("---")
            st.markdown("### 🎨 Towel Color Breakdown")
            col = df_mfg.groupby('Color').agg({'Mfg_Units':'sum','Order ID':'count'}) \
                        .rename(columns={'Mfg_Units':'Sets Needed','Order ID':'Line Items'}) \
                        .sort_values('Sets Needed', ascending=False)
            col['Sets Needed'] = col['Sets Needed'].astype(int)
            cols2 = st.columns(min(len(col), 4) or 1)
            for i, (t, r) in enumerate(col.iterrows()):
                with cols2[i % len(cols2)]:
                    st.metric(f"🎨 {t}", f"{r['Sets Needed']} sets", f"{r['Line Items']} items")

            st.markdown("---")
            st.markdown("### 📦 Product Type Breakdown")
            prod = df_mfg.groupby('Product Type').agg({'Quantity':'sum','Mfg_Units':'sum','Order ID':'count'}) \
                        .rename(columns={'Quantity':'Ordered Qty','Mfg_Units':'Production Units','Order ID':'Line Items'}) \
                        .sort_values('Production Units', ascending=False)
            prod['Ordered Qty'] = prod['Ordered Qty'].astype(int)
            prod['Production Units'] = prod['Production Units'].astype(int)
            st.dataframe(prod, use_container_width=True)

            st.markdown("---")
            st.markdown("### 🎯 Color × Thread Matrix")
            matrix = df_mfg.groupby(['Color','Thread Color'])['Mfg_Units'].sum().unstack(fill_value=0).astype(int)
            matrix['TOTAL'] = matrix.sum(axis=1); matrix.loc['TOTAL'] = matrix.sum()
            st.dataframe(matrix, use_container_width=True)

        with tab3:
            st.subheader("Manufacturing Labels")
            st.markdown("Select specific items to generate labels (6×4 inch landscape)")
            selected = []
            for idx, row in df.iterrows():
                c1, c2 = st.columns([0.1, 0.9])
                with c1:
                    if st.checkbox("", key=f"mfg_{idx}"):
                        selected.append(idx)
                with c2:
                    st.write(f"**{row['Order ID']}** — {row['Product Type']} — {row['Color']} — Qty: {row['Quantity']}")
            if selected:
                if st.button("🖨️ Generate Selected Labels", type="primary"):
                    with st.spinner("Generating labels..."):
                        output = BytesIO()
                        c = canvas.Canvas(output, pagesize=landscape((4 * inch, 6 * inch)))
                        for idx in selected:
                            row = df.loc[idx]
                            o = row['_order_obj']; it = row['_item_obj']
                            label_data = {
                                'order_id': o['order_id'], 'buyer': o['buyer_name'], 'date': o['order_date'],
                                'shipping': o['shipping_service'], 'quantity': it['quantity'],
                                'product_type': it['product_type'], 'towel_color': it['towel_color'],
                                'thread_color': it['font_color'], 'font': it['font'],
                                'customizations': it['customizations'], 'has_gift_note': bool(it['gift_message']),
                                'item_number': row['item_number'], 'item_count': row['item_count']
                            }
                            generate_manufacturing_label(c, label_data); c.showPage()
                        c.save(); output.seek(0)
                        st.download_button("📥 Download Manufacturing Labels PDF", output.getvalue(),
                                           "manufacturing_labels.pdf", "application/pdf")
                        st.success(f"✅ Generated {len(selected)} labels")
            else:
                st.info("Select items above to generate labels")

        with tab4:
            st.subheader("Gift Note Labels")
            gift_items = df[df['Gift Message'] == 'YES']
            if len(gift_items) == 0:
                st.info("No orders with gift messages found")
            else:
                st.markdown(f"**{len(gift_items)} orders with gift messages**")
                chosen = []
                for idx, row in gift_items.iterrows():
                    it = row['_item_obj']
                    c1, c2 = st.columns([0.1, 0.9])
                    with c1:
                        if st.checkbox("", key=f"gift_{idx}"):
                            chosen.append(idx)
                    with c2:
                        with st.expander(f"**{row['Order ID']}** — {row['Buyer']}"):
                            st.write(f"**Message:** {it['gift_message']}")
                if chosen:
                    if st.button("🎁 Generate Selected Gift Notes", type="primary"):
                        with st.spinner("Generating gift notes..."):
                            output = BytesIO()
                            c = canvas.Canvas(output, pagesize=landscape((4 * inch, 6 * inch)))
                            for idx in chosen:
                                row = gift_items.loc[idx]
                                o = row['_order_obj']; it = row['_item_obj']
                                generate_gift_note(c, o['order_id'], o['buyer_name'], it['gift_message'])
                                c.showPage()
                            c.save(); output.seek(0)
                            st.download_button("📥 Download Gift Notes PDF", output.getvalue(),
                                               "gift_notes.pdf", "application/pdf")
                            st.success(f"✅ Generated {len(chosen)} gift notes")
else:
    st.info("👆 Upload PDF files to get started")
