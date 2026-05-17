import streamlit as st
import pandas as pd
import sqlite3
import pdfplumber
import re
import io
from datetime import datetime

# ==========================================
# 1. ตั้งค่าฐานข้อมูลและฟังก์ชันที่เกี่ยวข้อง
# ==========================================
DB_NAME = "printer_management.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    # ตารางหลักเก็บข้อมูลเครื่อง
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

# สร้างข้อมูลเริ่มต้น (ถ้าฐานข้อมูลว่าง)
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
# 2. ฟังก์ชันอ่าน PDF ด้วย pdfplumber
# ==========================================
def extract_from_pdf(pdf_file):
    try:
        text = ""
        with pdfplumber.open(pdf_file) as pdf:
            for page in pdf.pages:
                text += page.extract_text() + "\n"
        
        # ค้นหา S/N
        sn_match = re.search(r'(RTL[0-9A-Z]+)', text, re.IGNORECASE)
        sn = sn_match.group(1).upper() if sn_match else None
        
        # ค้นหา Printed Pages
        page_match = re.search(r'Printed\s*Pages\D*?(\d+)', text, re.IGNORECASE)
        page_count = int(page_match.group(1)) if page_match else 0
        
        return sn, page_count, text
    except Exception as e:
        return None, 0, str(e)

# ==========================================
# 3. เริ่มสร้าง UI ด้วย Streamlit
# ==========================================
st.set_page_config(layout="wide", page_title="ระบบจัดการเครื่องพิมพ์")
init_db()
seed_data_if_empty()

# ทำเมนูนำทาง (Tabs) ด้านบน
tab1, tab2, tab3 = st.tabs(["🖨️ ระบบบันทึกมิเตอร์ (PDF)", "🔍 ค้นหาเครื่องพิมพ์แบบเร็ว", "⚙️ ตั้งค่าฐานข้อมูล (Config)"])

# ------------------------------------------
# TAB 1: ระบบบันทึกมิเตอร์จาก PDF
# ------------------------------------------
with tab1:
    st.header("ดึงข้อมูลจากไฟล์ Status Page (PDF)")
    
    col1, col2 = st.columns([1, 3])
    with col1:
        target_month = st.date_input("📅 เลือกรอบบิล", datetime.now()).strftime("%Y-%m")

    uploaded_files = st.file_uploader("ลากไฟล์ PDF มาวางที่นี่...", accept_multiple_files=True, type=['pdf'])
    extracted_data = {} 

    if uploaded_files:
        success_count = 0
        for file in uploaded_files:
            sn, p_count, raw_text = extract_from_pdf(file)
            
            if sn and p_count > 0:
                extracted_data[sn] = p_count
                success_count += 1
            else:
                st.error(f"⚠️ อ่านไฟล์ '{file.name}' สำเร็จ แต่หาข้อมูลไม่เจอ")
                with st.expander("🔍 คลิกดูข้อความดิบ (ช่วยหาจุดผิด)"):
                    st.text(raw_text if raw_text else "อ่านข้อความไม่ได้เลย (อาจเป็นไฟล์รูปภาพที่ถูกแปลงเป็น PDF)")
        
        if success_count > 0:
            st.success(f"✅ ดึงข้อมูลสำเร็จ {success_count} ไฟล์!")

    # แสดงตาราง
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

    st.markdown("*(คุณสามารถพิมพ์ตัวเลขในตารางเพื่อแก้ไขข้อมูลได้โดยตรง)*")
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
        label="📥 Export เป็น Excel (สำหรับเดือนนี้)",
        data=output.getvalue(),
        file_name=f"Report_{target_month}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

# ------------------------------------------
# TAB 2: ระบบค้นหาเครื่องพิมพ์ (ฟีเจอร์เดิม)
# ------------------------------------------
with tab2:
    st.header("🔍 ค้นหา S/N หรือ แผนก อย่างรวดเร็ว")
    st.markdown("พิมพ์คำที่ต้องการค้นหา (รองรับการหาหลายคำพร้อมกันโดยเว้นวรรค เช่น `1728 1872 ER`)")
    
    search_query = st.text_input("ช่องค้นหา:", placeholder="ตัวอย่าง: 1728 OR...")
    
    if search_query:
        df_search = load_master_data()
        search_terms = search_query.split()
        
        # ค้นหาในคอลัมน์ sn หรือ dept
        pattern = '|'.join(search_terms)
        result_df = df_search[
            df_search['sn'].str.contains(pattern, case=False, na=False) |
            df_search['dept'].str.contains(pattern, case=False, na=False)
        ]
        
        if not result_df.empty:
            st.success(f"✅ พบข้อมูล {len(result_df)} รายการ")
            st.dataframe(result_df.rename(columns={'sn': 'S/N', 'dept': 'แผนก'}), hide_index=True, use_container_width=True)
        else:
            st.error("❌ ไม่พบข้อมูลในระบบ")

# ------------------------------------------
# TAB 3: หน้า Config ข้อมูล
# ------------------------------------------
with tab3:
    st.header("⚙️ ตั้งค่าฐานข้อมูล S/N และ แผนก")
    st.markdown("คุณสามารถ **เพิ่ม ลบ หรือแก้ไข** ข้อมูลในตารางนี้ได้โดยตรง เมื่อแก้ไขเสร็จแล้วให้กดปุ่มบันทึกด้านล่าง ข้อมูลจะถูกนำไปใช้ในทุกหน้า")
    
    df_config = load_master_data()
    
    # อนุญาตให้แก้ไข เพิ่มลบแถวได้
    edited_config_df = st.data_editor(
        df_config,
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True
    )
    
    if st.button("💾 บันทึกการเปลี่ยนแปลงข้อมูล", type="primary"):
        save_master_data(edited_config_df)
        st.success("บันทึกข้อมูลเรียบร้อยแล้ว! ข้อมูลอัปเดตไปที่ระบบค้นหาและระบบบันทึกมิเตอร์แล้ว")
        st.rerun() # รีเฟรชหน้าเว็บเพื่อให้ข้อมูลอัปเดต
