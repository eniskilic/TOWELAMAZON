# 🚀 QUICK START GUIDE

## Get Running in 3 Steps

### 1️⃣ Install Dependencies
Open your terminal/command prompt and run:
```bash
pip install -r requirements.txt
```

### 2️⃣ Launch the App
```bash
streamlit run towel_order_app.py
```

The app will automatically open in your browser at `http://localhost:8501`

### 3️⃣ Start Processing Orders
1. **Upload** your Amazon packing slip PDFs
2. **Review** the parsed data in the table
3. **Select** items you want to print
4. **Download** the label PDFs
5. **Print** on 6×4 inch labels (landscape)

---

## Example Workflow

### For Manufacturing Team:
1. Upload all today's order PDFs
2. Go to "Manufacturing Labels" tab
3. Check all items
4. Click "Generate Selected Labels"
5. Print the PDF on thermal printer
6. Each label shows: Product, Color, Thread, Font, Personalization

### For Gift Orders:
1. Go to "Gift Notes" tab
2. Review which orders have gift messages
3. Select the ones you need
4. Click "Generate Selected Gift Notes"
5. Print on nice label paper
6. Attach gift notes to packages

---

## Printing Settings

**Thermal Printer:**
- Paper: 6×4 inch labels
- Orientation: Landscape
- Quality: Best/Darkest setting

**Regular Printer:**
- Paper: 6×4 inch label sheets OR cardstock
- Orientation: Landscape
- Scale: 100% (actual size)
- Color: Black & White is fine

---

## Tips for Best Results

✅ **Upload multiple PDFs at once** - The app handles batch processing  
✅ **Use filters** - Filter by product type or color to organize work  
✅ **Check gift messages** - Don't forget to print gift notes separately  
✅ **Print in batches** - Select multiple labels and print them all together  
✅ **Keep PDFs organized** - Name files by date for easy tracking  

---

## Need Help?

**App won't start?**
- Make sure Python 3.8+ is installed
- Run `pip install --upgrade streamlit` 

**PDFs not parsing?**
- Confirm they're Amazon Seller Central packing slips
- Check that "Order ID:" appears in the PDF

**Labels printing wrong size?**
- Disable "fit to page" in printer settings
- Set paper size to exactly 6×4 inches
- Use landscape orientation

---

**Ready to go? Run the app and start generating labels!** 🎯
