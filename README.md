# 🧺 Towel Order Parser & Label Generator

A Streamlit web application for parsing Amazon packing slip PDFs and generating print-ready manufacturing labels and gift notes for customized towel orders.

## Features

### 📋 PDF Parsing
- Parse Amazon Seller Central packing slip PDFs
- Extract order details: Order ID, date, buyer name, shipping service
- Parse product information: SKU, quantity, product type, color
- Extract customization details: font, thread color, personalization text
- Detect gift messages

### 🏷️ Manufacturing Labels (6×4 inch landscape)
- **Two-column layout optimized for thermal printing**
- **Left column (40%):** Product specs - Type, Color (ALL CAPS), Thread Color, Font
- **Right column (60%):** Personalization details for all pieces
- **Gift indicator:** Shows "GIFT NOTE: YES" when applicable
- **Black ink only** - No color backgrounds for thermal printers

### 🎁 Gift Note Labels (6×4 inch landscape)
- Elegant decorative design with borders and floral accents
- Centered gift message with automatic text wrapping
- Recipient name display
- Order reference for tracking

### 📊 Dashboard Features
- **Table view** with all parsed order data
- **Filters:** Product type, color, gift messages
- **Export:** CSV and Excel formats
- **Batch generation:** Select multiple items for label printing
- **Separate gift note generation**

## Supported Product Types

- **6-pc Set** (2 Washcloths, 2 Hand Towels, 2 Bath Towels)
- **3-pc Set** (1 Washcloth, 1 Hand Towel, 1 Bath Towel)
- **2-pc Bath Towel**
- **2-pc Hand Towel**
- **Bath Sheet (Oversized)**
- **Monogrammed Hand Towels**

## Installation

### Prerequisites
- Python 3.8 or higher
- pip package manager

### Setup

1. **Install dependencies:**
```bash
pip install -r requirements.txt
```

2. **Run the application:**
```bash
streamlit run towel_order_app.py
```

3. **Access the app:**
The app will open automatically in your browser at `http://localhost:8501`

## Usage

### Step 1: Upload PDFs
- Click "Upload PDF files" button
- Select one or more Amazon packing slip PDFs
- Wait for parsing to complete

### Step 2: Review Data (Table View Tab)
- View all parsed orders in table format
- Use filters to narrow down results:
  - Product Type
  - Color
  - Gift Messages (All/With Gift/No Gift)
- Export data to CSV or Excel if needed

### Step 3: Generate Manufacturing Labels
- Switch to "Manufacturing Labels" tab
- Check boxes next to items you want to print
- Click "Generate Selected Labels" button
- Download the PDF with all selected labels
- **Print on 6×4 inch labels in landscape orientation**

### Step 4: Generate Gift Notes (Optional)
- Switch to "Gift Notes" tab
- Review orders that have gift messages
- Check boxes next to gift notes you want to print
- Click "Generate Selected Gift Notes" button
- Download the PDF with all selected gift notes
- **Print on 6×4 inch labels in landscape orientation**

## Label Specifications

### Manufacturing Labels
- **Size:** 6×4 inches (landscape orientation)
- **Print:** Black ink only (thermal printer compatible)
- **Layout:** Two-column design
  - Order info header
  - Left: Product specifications (40%)
  - Right: Personalization details (60%)
  - Bottom: Gift note indicator

### Gift Note Labels
- **Size:** 6×4 inches (landscape orientation)
- **Print:** Black ink (decorative borders work well in color too)
- **Design:** Elegant with decorative elements
  - Double borders with floral corners
  - Centered gift message
  - Recipient name
  - Order reference

## Printing Tips

1. **Thermal Printer Settings:**
   - Set paper size to 6×4 inches
   - Use landscape orientation
   - Adjust darkness/contrast if needed

2. **Regular Printer:**
   - Use label sheets or cardstock
   - Set to landscape orientation
   - Print actual size (no scaling)

3. **Batch Printing:**
   - Select all items you need
   - Generate one PDF with all labels
   - Print entire batch at once

## Troubleshooting

### PDF Not Parsing
- Ensure the PDF is an Amazon Seller Central packing slip
- Check that the PDF contains "Order ID:" field
- Try uploading one file at a time

### Missing Customization Data
- Verify the PDF contains customization fields
- Check that "Choose Your Font" and personalization text are present

### Labels Not Printing Correctly
- Verify printer is set to landscape orientation
- Check paper size is set to 6×4 inches
- Ensure "fit to page" or scaling is disabled

## File Structure

```
towel_order_app.py      # Main Streamlit application
requirements.txt        # Python dependencies
README.md              # This file
```

## Technical Details

### PDF Parsing Logic
- Uses `pdfplumber` for text extraction
- Regex patterns for field extraction
- Multi-page order support with continuation detection
- Handles multiple items per order

### Label Generation
- Uses `reportlab` for PDF creation
- Precise measurements for 6×4 inch labels
- Optimized font sizes for readability
- Section borders for clear organization

## Support

For issues or questions:
- Check that all dependencies are installed correctly
- Verify PDF format matches Amazon Seller Central packing slips
- Ensure Python version is 3.8 or higher

## Version History

**v1.0** - Initial release
- PDF parsing for towel orders
- Two-column manufacturing labels
- Gift note label generation
- Dashboard with filters
- Batch export functionality

---

**Built for manufacturing efficiency and production quality** 🏭✨
