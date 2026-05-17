import streamlit as st
import pandas as pd
import sqlite3
import fitz  # PyMuPDF
import easyocr
import re
import io
from datetime import datetime

# ==========================================
# โหลดโมเดล AI ดวงตา (ทำแค่ครั้งเดียวตอนเปิดเว็บ)
# ==========================================
@st.cache_resource
def load_ocr_model():
    # ใช้แค่ภาษาอังกฤษ ('en') เพราะเราหาแค่เลข S/N กับ ตัวเลข Page Count เพื่อความรวดเร็ว
    return easyocr.Reader(['en'], gpu=False)

# ==========================================
# 1. ตั้งค่าฐานข้อมูล
# ==========================================
DB_NAME = "printer_management.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS master_data (sn TEXT PRIMARY KEY, dept TEXT)''')
    conn.commit()
    conn.close()

def load_master_data():
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql("SELECT sn, dept FROM master_data", conn)
    conn.close()
    return df

def save_master_data(df):
    conn = sqlite3.connect(DB_NAME)
    df.to_sql('master_data', conn, if_exists='replace', index=False)
    conn.close()

def seed_data_if_empty():
    df = load_master_data()
    if df.empty:
        initial_data = [
            {"sn": "RTL1101855", "dept": "Cashier B2"},
            {"sn": "RTL1101773", "dept": "Cashier OPD1"},
            {"sn": "RTL1101371", "dept": "Cashier IPD2"},
            {"sn": "RTL1101728", "dept": "OR"},
            {"sn": "RTL1101872", "dept": "Pharmacy A1"},
            {"sn": "RTL1402179", "dept": "Orthopedic"},
            {"sn": "RTL1101961", "dept": "IT Spare 2"},
            {"sn": "RTL1101905", "dept": "Pharmacy A2"}
        ]
        save_master_data(pd.DataFrame(initial_data))

# ==========================================
# 2. ฟังก์ชันอ่าน PDF + OCR AI
# ==========================================
def extract_from_pdf(pdf_file, reader):
    try:
        file_bytes = pdf_file.read()
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        text = ""
        is_ocr_used = False
        
        # 1. ลองอ่านแบบปกติก่อน (เร็วที่สุด)
        for page in doc:
            text += page.get_text("text") + "\n"
        
        # 2. ถ้าอ่านแล้วว่างเปล่า (เป็นไฟล์สแกน) ให้เรียกใช้ดวงตา OCR!
        if not text.strip():
            is_ocr_used = True
            text = ""
            for page in doc:
                # แปลงหน้า PDF เป็นรูปภาพความละเอียดสูง
                pix = page.get_pixmap(dpi=200)
                img_data = pix.tobytes("png")
                # ให้ AI อ่านตัวหนังสือจากรูปภาพ
                result = reader.readtext(img_data, detail=0)
                text += " ".join(result) + "\n"

        # 3. ล้างข้อความให้สะอาด (ลบช่องว่าง, ลูกน้ำ) เพื่อเตรียมหาตัวเลข
        clean_text = re.sub(r'[\s,"\'_:\-\.]', '', text).upper()
        
        # ค้นหา S/N 
        sn_match = re.search(r'(RTL[0-9A-Z]+)', clean_text)
        sn = sn_match.group(1) if sn_match else None
        
        # ค้นหา Printed Pages
        page_match = re.search(r'PRINTEDPAGES(\d+)', clean_text)
        page_count = int(page_match.group(1)) if page_match else 0
        
        # คืนค่ากลับไป พร้อมบอกว่าใช้ OCR ช่วยไหม
        return sn, page_count, text, is_ocr_used
    except Exception as e:
        return None, 0, f"Error: {str(e)}", False

# ==========================================
# 3. หน้า UI ของเว็บ
# ==========================================
st.set_page_config(layout="wide", page_title="ระบบจัดการเครื่องพิมพ์")
init_db()
seed_data_if_empty()

# โหลด AI เตรียมไว้
ocr_reader = load_ocr_model()

tab1, tab2, tab3 = st.tabs(["🖨️ ระบบบันทึกมิเตอร์ (PDF)", "🔍 ค้นหาเครื่องพิมพ์แบบเร็ว", "⚙️ ตั้งค่าฐานข้อมูล (Config)"])

with tab1:
    st.header("ดึงข้อมูลจากไฟล์ Status Page (รองรับไฟล์สแกน 100%)")
    col1, col2 = st.columns([1, 3])
    with col1:
        target_month = st.date_input("📅 เลือกรอบบิล", datetime.now()).strftime("%Y-%m")

    uploaded_files = st.file_uploader("ลากไฟล์ PDF มาวางที่นี่...", accept_multiple_files=True, type=['pdf'])
    extracted_data = {} 

    if uploaded_files:
        with st.spinner("⏳ กำลังใช้ AI อ่านเอกสาร (หากเป็นไฟล์สแกนอาจใช้เวลาสักครู่)..."):
            success_count = 0
            for file in uploaded_files:
                sn, p_count, raw_text, used_ocr = extract_from_pdf(file, ocr_reader)
                
                if sn and p_count > 0:
                    extracted_data[sn] = p_count
                    success_count += 1
                    if used_ocr:
                        st.info(f"👁️ อ่านไฟล์ '{file.name}' สำเร็จ! (ใช้ระบบ AI สแกนภาพช่วยอ่าน)")
                else:
                    st.error(f"⚠️ อ่านไฟล์ '{file.name}' สำเร็จ แต่หา S/N หรือ Page Count ไม่เจอ")
                    with st.expander("🔍 คลิกดูข้อความดิบที่ AI อ่านได้"):
                        st.text(raw_text)
            
            if success_count > 0:
                st.success(f"✅ ดึงข้อมูลสำเร็จรวม {success_count} ไฟล์! (ระบบกรอกลงตารางให้แล้ว)")

    df = load_master_data()
    df.rename(columns={'sn': 'S/N', 'dept': 'แผนก'}, inplace=True)
    df['เลขมิเตอร์ครั้งก่อน'] = 400000 
    df['เลขมิเตอร์ปัจจุบัน'] = 400000 

    def apply_extracted_count(row):
        if row['S/N'] in extracted_data:
            return extracted_data[row['S/N']]
        return row['เลขมิเตอร์ปัจจุบัน']

    df['เลขมิเตอร์ปัจจุบัน'] = df.apply(apply_extracted_count, axis=1)
    df['การใช้งาน (แผ่น)'] = 0

    st.markdown("*(พิมพ์ตัวเลขแก้ไขในช่อง 'เลขมิเตอร์ปัจจุบัน' ได้เลย)*")
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

    st.divider()
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        edited_df.to_excel(writer, index=False, sheet_name='Usage_Data')
    
    st.download_button(
        label="📥 Export เป็น Excel",
        data=output.getvalue(),
        file_name=f"Report_{target_month}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

with tab2:
    st.header("🔍 ค้นหา S/N หรือ แผนก อย่างรวดเร็ว")
    search_query = st.text_input("ช่องค้นหา:", placeholder="ตัวอย่าง: 1728 OR...")
    
    if search_query:
        df_search = load_master_data()
        search_terms = search_query.split()
        pattern = '|'.join(search_terms)
        result_df = df_search[
            df_search['sn'].str.contains(pattern, case=False, na=False) |
            df_search['dept'].str.contains(pattern, case=False, na=False)
        ]
        
        if not result_df.empty:
            st.dataframe(result_df.rename(columns={'sn': 'S/N', 'dept': 'แผนก'}), hide_index=True, use_container_width=True)
        else:
            st.error("❌ ไม่พบข้อมูลในระบบ")

with tab3:
    st.header("⚙️ ตั้งค่าฐานข้อมูล S/N และ แผนก")
    df_config = load_master_data()
    edited_config_df = st.data_editor(df_config, num_rows="dynamic", use_container_width=True, hide_index=True)
    
    if st.button("💾 บันทึกการเปลี่ยนแปลง", type="primary"):
        save_master_data(edited_config_df)
        st.success("บันทึกข้อมูลเรียบร้อยแล้ว!")
        st.rerun()
