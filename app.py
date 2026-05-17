import streamlit as st
import pandas as pd
import sqlite3
import PyPDF2
import re
import io
from datetime import datetime

# ==========================================
# 1. ตั้งค่าฐานข้อมูลและข้อมูลตั้งต้น
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
# 2. ฟังก์ชันสำหรับอ่านและดึงข้อมูลจาก PDF (อัปเดตใหม่!)
# ==========================================
def extract_from_pdf(pdf_file):
    try:
        reader = PyPDF2.PdfReader(pdf_file)
        text = ""
        for page in reader.pages:
            # ดึงข้อความมาต่อกัน
            text += page.extract_text() + "\n"
        
        # ค้นหา S/N (หาคำว่า RTL ตามด้วยตัวเลขและตัวอักษร)
        sn_match = re.search(r'(RTL[0-9A-Z]+)', text, re.IGNORECASE)
        sn = sn_match.group(1).upper() if sn_match else None
        
        # ค้นหา Printed Pages (ปรับให้ข้ามพวก , หรือ " หรือการขึ้นบรรทัดใหม่ ไปหาตัวเลข)
        # \D*? หมายถึง ให้ข้ามตัวอักษรอะไรก็ได้ที่ไม่ใช่ตัวเลข ไปเรื่อยๆ จนกว่าจะเจอตัวเลข (\d+)
        page_match = re.search(r'Printed\s*Pages\D*?(\d+)', text, re.IGNORECASE)
        page_count = int(page_match.group(1)) if page_match else 0
        
        return sn, page_count, text
    except Exception as e:
        return None, 0, str(e)

# ==========================================
# 3. หน้าจอเว็บแอปพลิเคชัน
# ==========================================
st.set_page_config(layout="wide", page_title="ระบบบันทึกมิเตอร์ PDF")
init_db()
seed_data()

st.title("🖨️ ระบบบันทึกมิเตอร์ (รองรับการ Import PDF)")

col1, col2 = st.columns([1, 3])
with col1:
    target_month = st.date_input("📅 เลือกรอบบิล / เดือน", datetime.now()).strftime("%Y-%m")

st.subheader("📁 นำเข้าไฟล์ Status Page (PDF)")
uploaded_files = st.file_uploader("ลากไฟล์ PDF มาวางที่นี่ (อัปโหลดพร้อมกันหลายไฟล์ได้)...", accept_multiple_files=True, type=['pdf'])

extracted_data = {} 

if uploaded_files:
    success_count = 0
    for file in uploaded_files:
        sn, p_count, raw_text = extract_from_pdf(file)
        
        # ถ้าระบุ S/N ได้ และหาเลขเจอ
        if sn and p_count > 0:
            extracted_data[sn] = p_count
            success_count += 1
        else:
            st.error(f"⚠️ อ่านไฟล์ '{file.name}' สำเร็จ แต่หา S/N หรือคำว่า Printed Pages ไม่เจอ")
            # ฟีเจอร์ใหม่: เอาไว้เปิดดูว่าโค้ดมันอ่าน PDF ออกมาเป็นภาษาต่างดาวหรือเปล่า
            with st.expander("🔍 คลิกเพื่อดูข้อความดิบที่ระบบอ่านได้ (ช่วยหาจุดผิด)"):
                st.text(raw_text[:1500]) # โชว์แค่ช่วงต้นๆ ให้ดู
    
    if success_count > 0:
        st.success(f"✅ ดึงข้อมูลสำเร็จ {success_count} ไฟล์ ระบบอัปเดตตัวเลขในตารางแล้ว!")

conn = sqlite3.connect(DB_NAME)
df = pd.read_sql("SELECT sn as 'S/N', dept as 'แผนก' FROM master_data", conn)

# จำลองเลขครั้งก่อน
df['เลขมิเตอร์ครั้งก่อน'] = 400000 
df['เลขมิเตอร์ปัจจุบัน'] = 400000 

def apply_extracted_count(row):
    sn = row['S/N']
    if sn in extracted_data:
        return extracted_data[sn]
    return row['เลขมิเตอร์ปัจจุบัน']

df['เลขมิเตอร์ปัจจุบัน'] = df.apply(apply_extracted_count, axis=1)
df['การใช้งาน (แผ่น)'] = 0

st.subheader(f"📊 ตารางบันทึกข้อมูลเดือน: {target_month}")
edited_df = st.data_editor(
    df,
    column_config={
        "S/N": st.column_config.TextColumn(disabled=True),
        "แผนก": st.column_config.TextColumn(disabled=True),
        "เลขมิเตอร์ครั้งก่อน": st.column_config.NumberColumn(disabled=True),
        "เลขมิเตอร์ปัจจุบัน": st.column_config.NumberColumn(),
        "การใช้งาน (แผ่น)": st.column_config.NumberColumn(disabled=True)
    },
    use_container_width=True,
    hide_index=True
)

edited_df['การใช้งาน (แผ่น)'] = edited_df['เลขมิเตอร์ปัจจุบัน'] - edited_df['เลขมิเตอร์ครั้งก่อน']

if (edited_df['การใช้งาน (แผ่น)'] < 0).any():
    st.warning("⚠️ แจ้งเตือน: มีบางรายการที่เลขปัจจุบันน้อยกว่าครั้งก่อน (ตรวจสอบ Usage ที่ติดลบ)")

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
