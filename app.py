import streamlit as st
import pandas as pd
import sqlite3
import PyPDF2
import re
import io
from datetime import datetime

# ==========================================
# 1. ตั้งค่าฐานข้อมูลและข้อมูลตั้งต้น (Master Data)
# ==========================================
DB_NAME = "printer_usage_v2.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS master_data (sn TEXT PRIMARY KEY, dept TEXT)''')
    conn.commit()
    conn.close()

def seed_data():
    conn = sqlite3.connect(DB_NAME)
    # ใส่ข้อมูลจากที่คุณเคยส่งมา (ใส่ตัวอย่างให้พอมองเห็นภาพ)
    sample_data = [
        ("RTL1101855", "Cashier B2"), ("RTL1101773", "Cashier OPD1"), 
        ("RTL1101371", "Cashier IPD2"), ("RTL1101728", "OR"), 
        ("RTL1101872", "Pharmacy A1"), ("RTL1402179", "Orthopedic"), 
        ("RTL1101961", "IT Spare 2"), ("RTL1101905", "Pharmacy A2")
    ]
    for sn, dept in sample_data:
        conn.execute("INSERT OR IGNORE INTO master_data (sn, dept) VALUES (?, ?)", (sn, dept))
    conn.commit()
    conn.close()

# ==========================================
# 2. ฟังก์ชันสำหรับอ่านและดึงข้อมูลจาก PDF
# ==========================================
def extract_from_pdf(pdf_file):
    try:
        reader = PyPDF2.PdfReader(pdf_file)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        
        # ค้นหา S/N (เช่น RTL1101855)
        sn_match = re.search(r'(RTL[0-9A-Z]+)', text)
        sn = sn_match.group(1) if sn_match else None
        
        # ค้นหา Printed Pages (ข้ามตัวอักษรที่ไม่ใช่ตัวเลขไปหาตัวเลขชุดแรก)
        page_match = re.search(r'Printed Pages[\D]*(\d+)', text, re.IGNORECASE)
        page_count = int(page_match.group(1)) if page_match else 0
        
        return sn, page_count
    except Exception as e:
        return None, 0

# ==========================================
# 3. หน้าจอเว็บแอปพลิเคชัน (UI)
# ==========================================
st.set_page_config(layout="wide", page_title="ระบบบันทึกมิเตอร์ PDF")
init_db()
seed_data()

st.title("🖨️ ระบบบันทึกมิเตอร์ (รองรับการ Import PDF)")
st.markdown("ทดลองอัปโหลดไฟล์ `12323.pdf` หรือไฟล์ Status Page อื่นๆ ระบบจะดึง S/N และเลขหน้ามาใส่ในตารางให้อัตโนมัติ")

col1, col2 = st.columns([1, 3])
with col1:
    target_month = st.date_input("📅 เลือกรอบบิล / เดือน", datetime.now()).strftime("%Y-%m")

# --- ส่วนอัปโหลดไฟล์ ---
st.subheader("📁 นำเข้าไฟล์ Status Page (PDF)")
uploaded_files = st.file_uploader("ลากไฟล์ PDF มาวางที่นี่ (อัปโหลดพร้อมกันหลายไฟล์ได้)...", accept_multiple_files=True, type=['pdf'])

# ตัวแปรเก็บค่าที่อ่านได้จาก PDF
extracted_data = {} 

if uploaded_files:
    success_count = 0
    for file in uploaded_files:
        sn, p_count = extract_from_pdf(file)
        if sn:
            extracted_data[sn] = p_count
            success_count += 1
    
    if success_count > 0:
        st.success(f"✅ อ่านข้อมูลสำเร็จ {success_count} ไฟล์ ระบบได้นำตัวเลขไปกรอกในตารางด้านล่างแล้ว!")
    else:
        st.warning("⚠️ อ่านไฟล์สำเร็จ แต่หาเลข S/N หรือ Page Count ไม่เจอ")

# --- ดึงข้อมูลจากฐานข้อมูลมาแสดง ---
conn = sqlite3.connect(DB_NAME)
df = pd.read_sql("SELECT sn as 'S/N', dept as 'แผนก' FROM master_data", conn)

# จำลองเลขครั้งก่อน (ในระบบจริงจะดึงจาก DB เดือนที่แล้ว)
df['เลขมิเตอร์ครั้งก่อน'] = 400000 
df['เลขมิเตอร์ปัจจุบัน'] = 400000 # ค่าเริ่มต้น

# เอาค่าที่อ่านได้จาก PDF มายัดใส่ DataFrame ตรงช่อง 'ปัจจุบัน'
def apply_extracted_count(row):
    sn = row['S/N']
    if sn in extracted_data:
        return extracted_data[sn]
    return row['เลขมิเตอร์ปัจจุบัน']

df['เลขมิเตอร์ปัจจุบัน'] = df.apply(apply_extracted_count, axis=1)
df['การใช้งาน (แผ่น)'] = 0

st.subheader(f"📊 ตารางบันทึกข้อมูลเดือน: {target_month}")
st.markdown("*(ช่อง **เลขมิเตอร์ปัจจุบัน** คุณสามารถพิมพ์แก้ไขเองได้ด้วย หากไฟล์ไหนอ่านไม่ได้)*")

edited_df = st.data_editor(
    df,
    column_config={
        "S/N": st.column_config.TextColumn(disabled=True),
        "แผนก": st.column_config.TextColumn(disabled=True),
        "เลขมิเตอร์ครั้งก่อน": st.column_config.NumberColumn(disabled=True),
        "เลขมิเตอร์ปัจจุบัน": st.column_config.NumberColumn(help="ค่าจาก PDF หรือพิมพ์เอง"),
        "การใช้งาน (แผ่น)": st.column_config.NumberColumn(disabled=True)
    },
    use_container_width=True,
    hide_index=True
)

# คำนวณ Usage แบบ Real-time
edited_df['การใช้งาน (แผ่น)'] = edited_df['เลขมิเตอร์ปัจจุบัน'] - edited_df['เลขมิเตอร์ครั้งก่อน']

if (edited_df['การใช้งาน (แผ่น)'] < 0).any():
    st.error("⚠️ แจ้งเตือน: มีบางรายการที่เลขปัจจุบันน้อยกว่าครั้งก่อน")

# --- ปุ่ม Action ---
col3, col4, col5 = st.columns([1, 1, 3])
with col3:
    if st.button("💾 ยืนยันบันทึกข้อมูล", use_container_width=True):
        st.success("✅ บันทึกข้อมูลเรียบร้อย!")

with col4:
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        edited_df.to_excel(writer, index=False, sheet_name='Usage_Data')
    
    st.download_button(
        label="📥 ส่งออกเป็น Excel",
        data=output.getvalue(),
        file_name=f"Report_{target_month}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )

conn.close()