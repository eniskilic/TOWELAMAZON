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

def parse_towel_orders(pdf_file):
    """Parse Amazon towel order PDFs"""
    orders = []
    
    with pdfplumber.open(pdf_file) as pdf:
        current_order = None
        
        for page in pdf.pages:
            text = page.extract_text()
            
            # Check if this is a new order (has "Order ID:")
            if 'Order ID:' in text:
                # Save previous order if exists
                if current_order and current_order['items']:
                    orders.append(current_order)
                
                # Start new order
                order_id_match = re.search(r'Order ID:\s*([\d-]+)', text)
                current_order = {
                    'order_id': order_id_match.group(1).strip() if order_id_match else '',
                    'order_date': '',
                    'buyer_name': '',
                    'shipping_service': '',
                    'items': []
                }
                
                # Extract metadata
                date_match = re.search(r'Order Date:\s*(.+?)(?:\n|Shipping)', text)
                if date_match:
                    current_order['order_date'] = date_match.group(1).strip()
                
                shipping_match = re.search(r'Shipping Service:\s*(.+?)(?:\n|Buyer)', text)
                if shipping_match:
                    current_order['shipping_service'] = shipping_match.group(1).strip()
                
                # Get buyer name from Ship To section
                ship_to_match = re.search(r'Ship To:\s*\n\s*(.+?)(?:\n)', text)
                if ship_to_match:
                    current_order['buyer_name'] = ship_to_match.group(1).strip()
            
            if current_order:
                # Extract line items
                sections = re.split(r'(SKU:\s*[^\n]+)', text)
                
                for i in range(1, len(sections), 2):
                    if i + 1 < len(sections):
                        sku_line = sections[i]
                        content = sections[i + 1]
                        
                        sku_match = re.search(r'SKU:\s*([^\n]+)', sku_line)
                        if not sku_match:
                            continue
                        
                        sku = sku_match.group(1).strip()
                        
                        # Find quantity
                        qty_match = re.search(r'Quantity[^\d]*(\d+)', text[:text.find(sku_line)])
                        quantity = qty_match.group(1) if qty_match else '1'
                        
                        # Extract customizations
                        font_match = re.search(r'Choose Your Font:\s*(.+?)(?:\n|Font Color)', content)
                        font = font_match.group(1).strip() if font_match else ''
                        
                        color_match = re.search(r'Font Color:\s*([^(#\n]+)', content)
                        font_color = color_match.group(1).strip() if color_match else ''
                        
                        # Parse SKU for product type and color
                        towel_color = sku.split('-')[-1].strip()
                        # Clean up color - remove any tax/price text that got captured
                        towel_color = re.split(r'\s+(?:Tax|Item|total|\$)', towel_color)[0].strip()
                        
                        customizations = []
                        product_type = ''
                        
                        if 'Set-6Pcs' in sku:
                            product_type = '6-pc Set'
                            fields = [
                                ('Washcloth 1', r'First Washcloth:\s*(.+?)(?:\n|Second)'),
                                ('Washcloth 2', r'Second Washcloth:\s*(.+?)(?:\n|First Hand)'),
                                ('Hand Towel 1', r'First Hand Towel:\s*(.+?)(?:\n|Second Hand)'),
                                ('Hand Towel 2', r'Second Hand Towel:\s*(.+?)(?:\n|First Bath)'),
                                ('Bath Towel 1', r'First Bath Towel:\s*(.+?)(?:\n|Second Bath)'),
                                ('Bath Towel 2', r'Second Bath Towel:\s*(.+?)(?:\n|Item|Grand|$)')
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
                            fields = [
                                ('Bath Sheet', r'Oversized Bath Sheet:\s*(.+?)(?:\n|Item|Grand|$)')
                            ]
                        else:
                            # Check for monogrammed hand towels
                            if 'Monogrammed Hand Towels' in text:
                                product_type = '2-pc Hand Towel (Monogrammed)'
                                initial_match = re.search(r'-\s*([A-Z])\s*$', sku)
                                if initial_match:
                                    initial = initial_match.group(1)
                                    customizations = [('Hand Towel 1', initial), ('Hand Towel 2', initial)]
                                    fields = None
                            else:
                                product_type = 'Unknown'
                                fields = None
                        
                        # Extract customization texts if fields defined
                        if 'fields' in locals() and fields:
                            for label, pattern in fields:
                                match = re.search(pattern, content)
                                if match:
                                    text_val = match.group(1).strip()
                                    customizations.append((label, text_val))
                        
                        # Check for gift message
                        gift_msg_match = re.search(r'Gift Message:\s*(.+?)(?:\n|Item|Grand|$)', content)
                        gift_message = gift_msg_match.group(1).strip() if gift_msg_match else ''
                        
                        # Check for gift card
                        gift_card_match = re.search(r'Add Gift Card:\s*(.+?)(?:\n|Item|Grand|$)', content)
                        if gift_card_match and not gift_message:
                            gift_message = gift_card_match.group(1).strip()
                        
                        item = {
                            'sku': sku,
                            'product_type': product_type,
                            'towel_color': towel_color,
                            'quantity': quantity,
                            'font': font,
                            'font_color': font_color,
                            'customizations': customizations,
                            'gift_message': gift_message
                        }
                        current_order['items'].append(item)
        
        if current_order and current_order['items']:
            orders.append(current_order)
    
    return orders

def generate_manufacturing_label(c, data, is_first=True):
    """Generate two-column manufacturing label"""
    W, H = landscape((4 * inch, 6 * inch))
    left = 0.25 * inch
    right = W - 0.25 * inch
    
    if is_first:
        y = H - 0.25 * inch
    else:
        y = H - 0.25 * inch
    
    # ============ HEADER: BUYER NAME & ORDER INFO ============
    # Buyer name (bold, 13pt)
    c.setFont("Helvetica-Bold", 13)
    c.drawString(left, y, data['buyer'])
    
    # QTY and Item Counter Badge
    qty_value = int(data['quantity'])
    
    # Show item counter badge only if order has multiple items
    if data['item_count'] > 1:
        # QTY label
        if qty_value > 2:
            c.setFont("Helvetica-BoldOblique", 15)
        else:
            c.setFont("Helvetica-Bold", 15)
        qty_text = f"QTY: {data['quantity']}"
        qty_width = c.stringWidth(qty_text, c._fontname, c._fontsize)
        c.drawRightString(right - 0.85 * inch, y, qty_text)
        
        # Item counter badge with warning triangle [2 of 3]
        c.setFont("Helvetica-Bold", 11)
        badge_text = f"▲ [{data['item_number']} of {data['item_count']}]"
        c.drawRightString(right, y, badge_text)
    else:
        # Single item - just show QTY
        if qty_value > 2:
            c.setFont("Helvetica-BoldOblique", 15)
        else:
            c.setFont("Helvetica-Bold", 15)
        c.drawRightString(right, y, f"QTY: {data['quantity']}")
    
    y -= 0.16 * inch
    
    # Order ID (regular, 11pt)
    c.setFont("Helvetica", 11)
    c.drawString(left, y, f"Order: {data['order_id']}")
    
    # Shipping
    c.setFont("Helvetica", 9)
    c.drawRightString(right, y, data['shipping'])
    y -= 0.15 * inch
    
    # Date
    c.setFont("Helvetica", 9)
    c.drawString(left, y, data['date'])
    y -= 0.22 * inch
    
    # Thick divider
    c.setStrokeColor(colors.black)
    c.setLineWidth(2)
    c.line(left, y, right, y)
    y -= 0.15 * inch
    
    # ============ TWO-COLUMN SECTION ============
    total_width = right - left
    left_col_width = total_width * 0.40
    right_col_width = total_width * 0.60
    
    left_col_right = left + left_col_width
    right_col_left = left_col_right + 0.1 * inch
    
    content_height = 2.4 * inch
    content_top = y
    content_bottom = y - content_height
    
    # Outer border
    c.setLineWidth(2)
    c.rect(left, content_bottom, right - left, content_height, stroke=1, fill=0)
    
    # Vertical divider
    c.setLineWidth(1.5)
    c.line(left_col_right + 0.05 * inch, content_top, 
           left_col_right + 0.05 * inch, content_bottom)
    
    # ========== LEFT COLUMN: PRODUCT SPECS ==========
    col_y = content_top - 0.12 * inch
    col_center = left + (left_col_width / 2)
    
    # Product Type (label + value with spacing)
    c.setFont("Helvetica", 8)
    c.drawCentredString(col_center, col_y, "PRODUCT TYPE:")
    col_y -= 0.2 * inch  # Increased spacing
    c.setFont("Helvetica-Bold", 11)  # Made BOLD
    c.drawCentredString(col_center, col_y, data['product_type'].upper())
    col_y -= 0.3 * inch  # More space before divider
    
    # Divider
    c.setLineWidth(0.5)
    c.line(left + 0.05 * inch, col_y, left_col_right - 0.05 * inch, col_y)
    col_y -= 0.22 * inch  # More space after divider
    
    # Color (ALL CAPS, centered, BOLD)
    c.setFont("Helvetica", 8)
    c.drawCentredString(col_center, col_y, "COLOR:")
    col_y -= 0.2 * inch  # Increased spacing
    c.setFont("Helvetica-Bold", 16)  # Made BOLD
    c.drawCentredString(col_center, col_y, data['towel_color'].upper())
    col_y -= 0.32 * inch  # More space before divider
    
    # Divider
    c.setLineWidth(0.5)
    c.line(left + 0.05 * inch, col_y, left_col_right - 0.05 * inch, col_y)
    col_y -= 0.22 * inch  # More space after divider
    
    # Thread Color (centered, BOLD)
    c.setFont("Helvetica", 8)
    c.drawCentredString(col_center, col_y, "THREAD COLOR:")
    col_y -= 0.18 * inch  # Increased spacing
    c.setFont("Helvetica-Bold", 13)  # Made BOLD
    c.drawCentredString(col_center, col_y, data['thread_color'].upper())
    
    # ========== RIGHT COLUMN: PERSONALIZATION ==========
    col_y = content_top - 0.12 * inch
    
    c.setFont("Helvetica-Bold", 9)
    c.drawString(right_col_left + 0.05 * inch, col_y, "PERSONALIZATION:")
    col_y -= 0.24 * inch  # More space after header
    
    for i, (label, text) in enumerate(data['customizations']):
        if col_y > content_bottom + 0.2 * inch:
            # Label (11pt, regular font)
            c.setFont("Helvetica", 11)
            c.drawString(right_col_left + 0.08 * inch, col_y, f"{label}:")
            col_y -= 0.18 * inch  # More space between label and text
            
            # Personalization text (15pt, bold italic)
            c.setFont("Helvetica-BoldOblique", 15)
            c.drawString(right_col_left + 0.08 * inch, col_y, text)
            col_y -= 0.24 * inch  # More space between items
    
    # ============ BOTTOM: GIFT MESSAGE BOX ============
    y_bottom = content_bottom - 0.15 * inch
    
    if data['has_gift_note']:
        gift_box_height = 0.25 * inch
        c.setLineWidth(2)
        c.rect(left, y_bottom - gift_box_height, right - left, gift_box_height, stroke=1, fill=0)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(left + 0.1 * inch, y_bottom - 0.16 * inch, "🎁 GIFT NOTE: YES")

def generate_gift_note(c, order_id, buyer_name, gift_message):
    """Generate elegant gift note label"""
    W, H = landscape((4 * inch, 6 * inch))
    
    # Decorative border
    margin = 0.4 * inch
    c.setStrokeColor(colors.HexColor('#8B4513'))
    c.setLineWidth(3)
    c.rect(margin, margin, W - 2*margin, H - 2*margin, stroke=1, fill=0)
    
    # Inner border
    c.setLineWidth(1)
    c.rect(margin + 0.1*inch, margin + 0.1*inch, 
           W - 2*margin - 0.2*inch, H - 2*margin - 0.2*inch, 
           stroke=1, fill=0)
    
    # Decorative corners
    corners = [
        (margin + 0.15*inch, H - margin - 0.15*inch),
        (W - margin - 0.15*inch, H - margin - 0.15*inch),
        (margin + 0.15*inch, margin + 0.15*inch),
        (W - margin - 0.15*inch, margin + 0.15*inch)
    ]
    
    c.setFont("Helvetica", 16)
    c.setFillColor(colors.HexColor('#D4A574'))
    for x, y in corners:
        c.drawCentredString(x, y - 0.05*inch, "❀")
    
    # Heart at top
    c.setFont("Helvetica", 20)
    c.setFillColor(colors.HexColor('#C64A7B'))
    c.drawCentredString(W / 2, H - margin - 0.5*inch, "♥")
    
    # Gift message (centered, wrapped)
    y = H / 2 + 0.3 * inch
    c.setFont("Helvetica-Oblique", 14)
    c.setFillColor(colors.HexColor('#4A4A4A'))
    
    max_width = W - 2*margin - 0.8*inch
    lines = simpleSplit(gift_message, "Helvetica-Oblique", 14, max_width)
    
    for line in lines:
        c.drawCentredString(W / 2, y, line)
        y -= 0.22 * inch
    
    # Recipient name at bottom
    c.setFont("Helvetica-Bold", 12)
    c.setFillColor(colors.HexColor('#8B4513'))
    c.drawCentredString(W / 2, margin + 0.6*inch, f"To: {buyer_name}")
    
    # Order reference
    c.setFont("Helvetica", 7)
    c.setFillColor(colors.grey)
    c.drawRightString(W - margin - 0.15*inch, margin + 0.2*inch, f"Order: {order_id}")

# ==================== STREAMLIT APP ====================

st.title("🧺 Towel Order Parser & Label Generator")
st.markdown("**Upload Amazon packing slip PDFs to generate manufacturing labels**")

# File uploader
uploaded_files = st.file_uploader(
    "Upload PDF files", 
    type=['pdf'], 
    accept_multiple_files=True,
    help="Upload one or more Amazon packing slip PDFs"
)

if uploaded_files:
    # Clear previous session data when new files are uploaded
    st.session_state['mfg_labels_pdf'] = None
    st.session_state['gift_notes_pdf'] = None
    
    # Parse all files
    all_orders = []
    
    with st.spinner("Parsing PDFs..."):
        for uploaded_file in uploaded_files:
            try:
                orders = parse_towel_orders(uploaded_file)
                all_orders.extend(orders)
            except Exception as e:
                st.error(f"Error parsing {uploaded_file.name}: {e}")
    
    if all_orders:
        # Create flat list for display
        records = []
        for order in all_orders:
            for item in order['items']:
                records.append({
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
                    '_order_obj': order,
                    '_item_obj': item
                })
        
        df = pd.DataFrame(records)
        # Reset index to start from 1 instead of 0
        df.index = range(1, len(df) + 1)
        
        # Add item counter for multi-item orders
        df['item_count'] = df.groupby('Order ID')['Order ID'].transform('count')
        df['item_number'] = df.groupby('Order ID').cumcount() + 1
        
        st.success(f"✅ Parsed {len(all_orders)} orders with {len(df)} items")
        
        # Create tabs
        tab1, tab2, tab3, tab4 = st.tabs(["📊 Table View", "📋 Manufacturing Plan", "🏷️ Manufacturing Labels", "🎁 Gift Notes"])
        
        with tab1:
            st.subheader("Order Data")
            
            # Display table (no filters)
            display_df = df.drop(columns=['_order_obj', '_item_obj'])
            st.dataframe(display_df, use_container_width=True, height=400)
            
            # Generate ALL Manufacturing Labels button (with download button next to it)
            col1, col2 = st.columns(2)
            with col1:
                generate_clicked = st.button("🏷️ Generate ALL Manufacturing Labels", type="primary", use_container_width=True)
            
            with col2:
                # Empty placeholder - will be filled after generation
                download_placeholder = st.empty()
            
            if generate_clicked:
                with st.spinner("Generating all manufacturing labels..."):
                    output = BytesIO()
                    c = canvas.Canvas(output, pagesize=landscape((4 * inch, 6 * inch)))
                    
                    for idx, row in df.iterrows():
                        order_obj = row['_order_obj']
                        item_obj = row['_item_obj']
                        
                        label_data = {
                            'order_id': order_obj['order_id'],
                            'buyer': order_obj['buyer_name'],
                            'date': order_obj['order_date'],
                            'shipping': order_obj['shipping_service'],
                            'quantity': item_obj['quantity'],
                            'product_type': item_obj['product_type'],
                            'towel_color': item_obj['towel_color'],
                            'thread_color': item_obj['font_color'],
                            'font': item_obj['font'],
                            'customizations': item_obj['customizations'],
                            'has_gift_note': bool(item_obj['gift_message']),
                            'item_number': row['item_number'],
                            'item_count': row['item_count']
                        }
                        
                        generate_manufacturing_label(c, label_data)
                        c.showPage()
                    
                    c.save()
                    output.seek(0)
                    
                    # Store in session state
                    st.session_state['mfg_labels_pdf'] = output.getvalue()
                    st.success(f"✅ Generated {len(df)} manufacturing labels")
                    
                    # Show download button immediately after generation
                    with download_placeholder:
                        st.download_button(
                            "📥 Download PDF",
                            st.session_state['mfg_labels_pdf'],
                            "all_manufacturing_labels.pdf",
                            "application/pdf",
                            use_container_width=True,
                            key="download_mfg_after_gen"
                        )
            elif 'mfg_labels_pdf' in st.session_state and st.session_state['mfg_labels_pdf']:
                # Show download button if labels exist from this session
                with download_placeholder:
                    st.download_button(
                        "📥 Download PDF",
                        st.session_state['mfg_labels_pdf'],
                        "all_manufacturing_labels.pdf",
                        "application/pdf",
                        use_container_width=True,
                        key="download_mfg_existing"
                    )
            
            # Export buttons (side by side, below manufacturing labels)
            col1, col2 = st.columns(2)
            with col1:
                csv = display_df.to_csv(index=True).encode('utf-8')
                st.download_button(
                    "📥 Export to CSV",
                    csv,
                    "towel_orders.csv",
                    "text/csv",
                    use_container_width=True
                )
            
            with col2:
                buffer = BytesIO()
                with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                    display_df.to_excel(writer, index=True, sheet_name='Orders')
                st.download_button(
                    "📥 Export to Excel",
                    buffer.getvalue(),
                    "towel_orders.xlsx",
                    "application/vnd.ms-excel",
                    use_container_width=True
                )
            
            st.markdown("---")
            
            # Generate ALL Gift Notes button (only for items with gift messages)
            gift_items_count = len(df[df['Gift Message'] == 'YES'])
            
            if gift_items_count > 0:
                col1, col2 = st.columns(2)
                with col1:
                    gift_generate_clicked = st.button(f"🎁 Generate ALL Gift Notes ({gift_items_count} items)", type="secondary", use_container_width=True)
                
                with col2:
                    # Empty placeholder - will be filled after generation
                    gift_download_placeholder = st.empty()
                
                if gift_generate_clicked:
                    with st.spinner("Generating all gift notes..."):
                        output = BytesIO()
                        c = canvas.Canvas(output, pagesize=landscape((4 * inch, 6 * inch)))
                        
                        count = 0
                        for idx, row in df.iterrows():
                            if row['Gift Message'] == 'YES':
                                order_obj = row['_order_obj']
                                item_obj = row['_item_obj']
                                
                                generate_gift_note(
                                    c, 
                                    order_obj['order_id'],
                                    order_obj['buyer_name'],
                                    item_obj['gift_message']
                                )
                                c.showPage()
                                count += 1
                        
                        c.save()
                        output.seek(0)
                        
                        # Store in session state
                        st.session_state['gift_notes_pdf'] = output.getvalue()
                        st.success(f"✅ Generated {count} gift notes")
                        
                        # Show download button immediately after generation
                        with gift_download_placeholder:
                            st.download_button(
                                "📥 Download PDF",
                                st.session_state['gift_notes_pdf'],
                                "all_gift_notes.pdf",
                                "application/pdf",
                                use_container_width=True,
                                key="download_gift_after_gen"
                            )
                elif 'gift_notes_pdf' in st.session_state and st.session_state['gift_notes_pdf']:
                    # Show download button if gift notes exist from this session
                    with gift_download_placeholder:
                        st.download_button(
                            "📥 Download PDF",
                            st.session_state['gift_notes_pdf'],
                            "all_gift_notes.pdf",
                            "application/pdf",
                            use_container_width=True,
                            key="download_gift_existing"
                        )
            else:
                st.info("ℹ️ No gift messages in current orders")
        
        with tab2:
            st.subheader("📋 Manufacturing Plan - Production Summary")
            st.markdown("*Daily production overview organized by thread color, towel color, and product type*")
            
            # Convert 6-pc sets to manufacturing units (2x 3-pc sets)
            df_mfg = df.copy()
            
            # Calculate manufacturing units
            # 6-pc set = 2 washcloths + 2 hand towels + 2 bath towels (treat as 2x 3-pc for production)
            def calc_mfg_units(row):
                qty = int(row['Quantity'])
                product = row['Product Type']
                
                if '6-pc' in product.lower():
                    return qty * 2  # 6-pc set = 2 production units
                else:
                    return qty
            
            df_mfg['Mfg_Units'] = df_mfg.apply(calc_mfg_units, axis=1)
            
            # Overall Summary
            st.markdown("### 📊 Overall Summary")
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Total Orders", len(df['Order ID'].unique()))
            with col2:
                st.metric("Total Line Items", len(df))
            with col3:
                total_sets = df_mfg['Mfg_Units'].sum()
                st.metric("Production Units", int(total_sets))
            with col4:
                gift_count = len(df[df['Gift Message'] == 'YES'])
                st.metric("Gift Notes", gift_count)
            
            st.markdown("---")
            
            # Thread Color Breakdown
            st.markdown("### 🧵 Thread Color Breakdown")
            st.markdown("*Number of towel sets to embroider in each thread color*")
            
            thread_summary = df_mfg.groupby('Thread Color').agg({
                'Mfg_Units': 'sum',
                'Order ID': 'count'
            }).rename(columns={'Mfg_Units': 'Sets to Embroider', 'Order ID': 'Line Items'})
            thread_summary = thread_summary.sort_values('Sets to Embroider', ascending=False)
            thread_summary['Sets to Embroider'] = thread_summary['Sets to Embroider'].astype(int)
            
            # Display as columns for easy scanning
            thread_cols = st.columns(min(len(thread_summary), 4))
            for idx, (thread_color, row) in enumerate(thread_summary.iterrows()):
                with thread_cols[idx % 4]:
                    st.metric(
                        label=f"🧵 {thread_color}",
                        value=f"{row['Sets to Embroider']} sets",
                        delta=f"{row['Line Items']} items"
                    )
            
            st.markdown("---")
            
            # Towel Color Breakdown
            st.markdown("### 🎨 Towel Color Breakdown")
            st.markdown("*Number of towel sets needed in each color*")
            
            color_summary = df_mfg.groupby('Color').agg({
                'Mfg_Units': 'sum',
                'Order ID': 'count'
            }).rename(columns={'Mfg_Units': 'Sets Needed', 'Order ID': 'Line Items'})
            color_summary = color_summary.sort_values('Sets Needed', ascending=False)
            color_summary['Sets Needed'] = color_summary['Sets Needed'].astype(int)
            
            # Display as columns
            color_cols = st.columns(min(len(color_summary), 4))
            for idx, (color, row) in enumerate(color_summary.iterrows()):
                with color_cols[idx % 4]:
                    st.metric(
                        label=f"🎨 {color}",
                        value=f"{row['Sets Needed']} sets",
                        delta=f"{row['Line Items']} items"
                    )
            
            st.markdown("---")
            
            # Product Type Breakdown
            st.markdown("### 📦 Product Type Breakdown")
            st.markdown("*6-pc sets are counted as 2 production units (2x 3-pc sets)*")
            
            product_summary = df_mfg.groupby('Product Type').agg({
                'Quantity': 'sum',
                'Mfg_Units': 'sum',
                'Order ID': 'count'
            }).rename(columns={'Quantity': 'Ordered Qty', 'Mfg_Units': 'Production Units', 'Order ID': 'Line Items'})
            product_summary = product_summary.sort_values('Production Units', ascending=False)
            product_summary['Ordered Qty'] = product_summary['Ordered Qty'].astype(int)
            product_summary['Production Units'] = product_summary['Production Units'].astype(int)
            
            st.dataframe(product_summary, use_container_width=True)
            
            st.markdown("---")
            
            # Detailed Color x Thread Matrix
            st.markdown("### 🎯 Color × Thread Matrix")
            st.markdown("*Production units needed for each color/thread combination*")
            
            matrix_data = df_mfg.groupby(['Color', 'Thread Color'])['Mfg_Units'].sum().unstack(fill_value=0)
            matrix_data = matrix_data.astype(int)
            
            # Add row and column totals
            matrix_data['TOTAL'] = matrix_data.sum(axis=1)
            matrix_data.loc['TOTAL'] = matrix_data.sum()
            
            st.dataframe(matrix_data, use_container_width=True)
            
            st.markdown("---")
            
            # Production Checklist
            st.markdown("### ✅ Production Checklist")
            
            checklist_col1, checklist_col2 = st.columns(2)
            
            with checklist_col1:
                st.markdown("**🧵 Thread Setup Required:**")
                for thread_color in thread_summary.index:
                    count = int(thread_summary.loc[thread_color, 'Sets to Embroider'])
                    st.checkbox(f"{thread_color} ({count} sets)", key=f"thread_check_{thread_color}")
            
            with checklist_col2:
                st.markdown("**🎨 Towel Colors Needed:**")
                for color in color_summary.index:
                    count = int(color_summary.loc[color, 'Sets Needed'])
                    st.checkbox(f"{color} ({count} sets)", key=f"color_check_{color}")
        
        with tab3:
            st.subheader("Manufacturing Labels")
            st.markdown("Select specific items to generate labels (6×4 inch landscape)")
            
            # Selection
            selected_indices = []
            for idx, row in df.iterrows():
                col1, col2 = st.columns([0.1, 0.9])
                with col1:
                    if st.checkbox("", key=f"mfg_{idx}"):
                        selected_indices.append(idx)
                with col2:
                    st.write(f"**{row['Order ID']}** - {row['Product Type']} - {row['Color']} - Qty: {row['Quantity']}")
            
            if selected_indices:
                if st.button("🖨️ Generate Selected Labels", type="primary"):
                    with st.spinner("Generating labels..."):
                        output = BytesIO()
                        c = canvas.Canvas(output, pagesize=landscape((4 * inch, 6 * inch)))
                        
                        for idx in selected_indices:
                            row = df.loc[idx]
                            order_obj = row['_order_obj']
                            item_obj = row['_item_obj']
                            
                            label_data = {
                                'order_id': order_obj['order_id'],
                                'buyer': order_obj['buyer_name'],
                                'date': order_obj['order_date'],
                                'shipping': order_obj['shipping_service'],
                                'quantity': item_obj['quantity'],
                                'product_type': item_obj['product_type'],
                                'towel_color': item_obj['towel_color'],
                                'thread_color': item_obj['font_color'],
                                'font': item_obj['font'],
                                'customizations': item_obj['customizations'],
                                'has_gift_note': bool(item_obj['gift_message']),
                                'item_number': row['item_number'],
                                'item_count': row['item_count']
                            }
                            
                            generate_manufacturing_label(c, label_data)
                            c.showPage()
                        
                        c.save()
                        output.seek(0)
                        
                        st.download_button(
                            "📥 Download Manufacturing Labels PDF",
                            output.getvalue(),
                            "manufacturing_labels.pdf",
                            "application/pdf"
                        )
                        st.success(f"✅ Generated {len(selected_indices)} labels")
            else:
                st.info("Select items above to generate labels")
        
        with tab4:
            st.subheader("Gift Note Labels")
            
            # Filter items with gift messages
            gift_items = df[df['Gift Message'] == 'YES']
            
            if len(gift_items) > 0:
                st.markdown(f"**{len(gift_items)} orders with gift messages**")
                
                selected_gift_indices = []
                for idx, row in gift_items.iterrows():
                    item_obj = row['_item_obj']
                    col1, col2 = st.columns([0.1, 0.9])
                    with col1:
                        if st.checkbox("", key=f"gift_{idx}"):
                            selected_gift_indices.append(idx)
                    with col2:
                        with st.expander(f"**{row['Order ID']}** - {row['Buyer']}"):
                            st.write(f"**Message:** {item_obj['gift_message']}")
                
                if selected_gift_indices:
                    if st.button("🎁 Generate Selected Gift Notes", type="primary"):
                        with st.spinner("Generating gift notes..."):
                            output = BytesIO()
                            c = canvas.Canvas(output, pagesize=landscape((4 * inch, 6 * inch)))
                            
                            for idx in selected_gift_indices:
                                row = gift_items.loc[idx]
                                order_obj = row['_order_obj']
                                item_obj = row['_item_obj']
                                
                                generate_gift_note(
                                    c, 
                                    order_obj['order_id'],
                                    order_obj['buyer_name'],
                                    item_obj['gift_message']
                                )
                                c.showPage()
                            
                            c.save()
                            output.seek(0)
                            
                            st.download_button(
                                "📥 Download Gift Notes PDF",
                                output.getvalue(),
                                "gift_notes.pdf",
                                "application/pdf"
                            )
                            st.success(f"✅ Generated {len(selected_gift_indices)} gift notes")
                else:
                    st.info("Select gift notes above to generate")
            else:
                st.info("No orders with gift messages found")
else:
    st.info("👆 Upload PDF files to get started")
