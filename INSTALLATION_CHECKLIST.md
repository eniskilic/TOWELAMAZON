# ✅ INSTALLATION CHECKLIST

## Before You Start
- [ ] Python 3.8 or higher installed
- [ ] Terminal/Command Prompt access
- [ ] Downloaded all files from outputs folder

---

## Step-by-Step Installation

### ☐ Step 1: Open Terminal
**Windows:** Press `Win + R`, type `cmd`, press Enter  
**Mac:** Press `Cmd + Space`, type `terminal`, press Enter  
**Linux:** Press `Ctrl + Alt + T`

### ☐ Step 2: Navigate to App Folder
```bash
cd /path/to/towel_order_app
```
(Replace with the actual folder path where you saved the files)

### ☐ Step 3: Install Dependencies
```bash
pip install -r requirements.txt
```

**Wait for installation to complete** ⏳

Expected output:
```
Successfully installed streamlit-1.39.0 pdfplumber-0.11.4 ...
```

### ☐ Step 4: Launch the App
```bash
streamlit run towel_order_app.py
```

**The app will automatically open in your browser!** 🎉

---

## Verify Installation

### ✅ You should see:
- Browser opens to `http://localhost:8501`
- Page title: "🧺 Towel Order Parser & Label Generator"
- File upload button visible
- No error messages

### ❌ If you see errors:

**"streamlit: command not found"**
```bash
pip install --upgrade streamlit
```

**"No module named 'pdfplumber'"**
```bash
pip install pdfplumber reportlab pandas xlsxwriter
```

**"Permission denied"**
```bash
pip install --user -r requirements.txt
```

---

## First Test Run

### ☐ Test with Sample PDFs
1. Click "Upload PDF files"
2. Select your Amazon packing slip PDFs
3. Wait for parsing (should be fast - seconds)
4. Check that orders appear in table

### ☐ Generate Test Label
1. Go to "Manufacturing Labels" tab
2. Check one item
3. Click "Generate Selected Labels"
4. Download and open the PDF
5. Verify it shows correct information

### ☐ Test Print (Optional)
1. Open the generated PDF
2. Print settings:
   - Paper: 6×4 inches
   - Orientation: Landscape
   - Scale: 100% / Actual size
3. Print one test label
4. Verify it fits your label sheets

---

## Daily Workflow Setup

### Recommended Folder Structure:
```
📁 TowelOrders/
├── 📄 towel_order_app.py
├── 📄 requirements.txt
├── 📄 README.md
├── 📄 QUICK_START.md
├── 📁 pdfs_to_process/
│   └── (put new PDFs here)
├── 📁 labels_generated/
│   └── (save generated labels here)
└── 📁 processed_pdfs/
    └── (move processed PDFs here)
```

---

## Quick Commands Reference

### Start the app:
```bash
streamlit run towel_order_app.py
```

### Stop the app:
Press `Ctrl + C` in terminal

### Restart after updates:
Stop the app (Ctrl + C), then start again

### Update dependencies:
```bash
pip install --upgrade -r requirements.txt
```

---

## Troubleshooting Common Issues

### Issue: "Address already in use"
**Solution:** Another instance is running
```bash
# Kill the process and restart
pkill -f streamlit
streamlit run towel_order_app.py
```

### Issue: Browser doesn't open
**Solution:** Manually open browser
1. Look for this in terminal: `Local URL: http://localhost:8501`
2. Copy and paste URL into browser

### Issue: PDFs not parsing correctly
**Solution:** Check PDF format
- Must be Amazon Seller Central packing slips
- Must contain "Order ID:" field
- Try uploading one file at a time first

### Issue: Labels printing wrong size
**Solution:** Check printer settings
- Set paper size to EXACTLY 6×4 inches
- Set orientation to Landscape
- Disable "Fit to page"
- Set scale to 100%

---

## Performance Notes

**Expected Speed:**
- Upload: Instant
- Parsing: 1-2 seconds per order
- Label generation: ~0.5 seconds per label
- 100 orders = ~5 minutes total

**Browser Compatibility:**
- ✅ Chrome (recommended)
- ✅ Firefox
- ✅ Safari
- ✅ Edge

---

## You're All Set! 🎉

**Everything installed and working?**  
Check all boxes above ✅

**Ready to process orders?**  
Open the app and start uploading PDFs! 📤

**Need help?**  
Check README.md for detailed documentation 📖

---

**Pro Tip:** Bookmark `http://localhost:8501` in your browser for quick access! 🔖
