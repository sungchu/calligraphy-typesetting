import re
import time
import random
import streamlit as st
from streamlit_image_select import image_select
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.core.os_manager import ChromeType
from collections import defaultdict
import os
from zhconv import convert
from PIL import Image
import requests
from io import BytesIO

# ================= 初始化 session_state =================
if "results" not in st.session_state:
    st.session_state.results = []
if "selected_images" not in st.session_state:
    st.session_state.selected_images = []
if "display_index" not in st.session_state:
    st.session_state.display_index = {}

st.title("書法字典圖片瀏覽器")
st.markdown(
    """
    <style>
    .stImage img {
        width: 60px !important;   /* 強制寬度 */
        height: auto !important;   /* 保持比例 */
        border-radius: 0 !important; /* 順便把圓角也拿掉 */
    }
    </style>
    """,
    unsafe_allow_html=True
)

search_input = st.text_input("請輸入要搜尋的文字（標點符號將自動忽略，可同時輸入多個字，建議長度不超過30字）")
search_input_chinese = "".join(re.findall(r"[\u4e00-\u9fff]+", search_input))
style_dict = {"1": "章草", "3": "篆書", "4": "簡牘", "5": "魏碑",
              "6": "隸書", "7": "草書", "8": "行書", "9": "楷書"}
style_value = st.selectbox("選擇書法字體",
                           options=list(style_dict.keys()),
                           format_func=lambda x: style_dict[x],
                           index=7)

filter_calligrapher_input = st.text_input(
    "指定特定書法家（若想指定多位，請用、分隔，留空則代表不指定 e.g. 王羲之、顏真卿、歐陽詢）", ""
)
if filter_calligrapher_input.strip():
    filter_calligrapher_list = [c.strip() for c in filter_calligrapher_input.split("、") if c.strip()]
else:
    filter_calligrapher_list = None

download_limit = 4
placeholder_img_path = os.path.join(os.getcwd(), "查無此字.png")  # 同資料夾下

# ================= 安全顯示圖片 =================
def safe_show_image(img_url, width=120):
    try:
        if not img_url:
            img = Image.open(placeholder_img_path)
            st.image(img, width=width)
            return

        if isinstance(img_url, str) and img_url.startswith("http"):
            resp = requests.get(img_url, timeout=5)
            if resp.status_code != 200:
                st.write("⚠️ 圖片下載失敗")
                return
            img = Image.open(BytesIO(resp.content))
            st.image(img, width=width)
        else:
            # 假設是本地檔案
            if os.path.exists(img_url):
                img = Image.open(img_url)
                st.image(img, width=width)
            else:
                st.write("⚠️ 找不到圖片檔案")
    except Exception as e:
        st.write(f"⚠️ 無法顯示圖片：{e}")

# ================= 下載word =================
from docx import Document
from docx.shared import Cm, Pt
from io import BytesIO
import requests
from PIL import Image

def download_word(selected_data):
    """
    selected_data: list of tuples (idx, word, author, img_url)
    """

    # 建立 Word 文件
    doc = Document()

    # 建立表格：16 橫排、4 直行
    table = doc.add_table(rows=16, cols=4)
    table.autofit = False

    # 設定行高：單數行高 1、偶數行高 3
    for i, row in enumerate(table.rows):
        if (i+1) % 2 == 1:  # 單數行
            row.height = Cm(1)
        else:  # 偶數行
            row.height = Cm(3)

    # 資料排序（從右上往下）
    sorted_selected = sorted(selected_data, key=lambda x: x[0])

    # 建立交替資料：word → image → word → image
    layout_items = []
    for _, word, author, img_url in sorted_selected:
        layout_items.append(("word", word))
        layout_items.append(("image", img_url))

    # 從右上角開始填（先列後行）
    total_cells = 16 * 4
    for idx, item in enumerate(layout_items[:total_cells]):
        row = idx % 16  # 行
        col = 3 - (idx // 16)  # 右到左的列（0→左,3→右）
        cell = table.cell(row, col)

        if item[0] == "word":
            # 插入文字
            p = cell.paragraphs[0]
            run = p.add_run(item[1])
            run.font.size = Pt(16)
        else:
            # 插入圖片
            img_url = item[1]
            try:
                response = requests.get(img_url)
                image = Image.open(BytesIO(response.content))
                image_stream = BytesIO()
                image.save(image_stream, format="PNG")
                image_stream.seek(0)
                cell.paragraphs[0].add_run().add_picture(image_stream, width=Inches(0.8))
            except Exception as e:
                cell.text = "[圖片載入失敗]"

    # 存到記憶體
    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer

# ================= 搜尋按鈕 =================
if st.button("開始搜尋"):
    st.session_state.results = []
    st.session_state.selected_images = []
    st.session_state.display_index = {}

    search_words = list(search_input_chinese.strip())
    results = []
    total_words = len(search_words)
    progress_bar = st.progress(0, text='搜尋中，請稍後')
    status_text = st.empty()

    # Spinner 轉圈圈
    with st.spinner("🔄 搜尋中，請稍後..."):
        # ================= Selenium 設定 =================
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--incognito")
        options.add_argument("--disable-dev-shm-usage")
        service = Service(ChromeDriverManager(chrome_type=ChromeType.CHROMIUM).install())

        driver = None
        try:
            driver = webdriver.Chrome(service=service, options=options)
            base_url = "https://www.shufazidian.com/s.php"
            start_time = time.time()

            for idx, word in enumerate(search_words):
                word_found = False
                try:
                    driver.get(base_url)
                    time.sleep(random.uniform(1, 2))

                    search_input_elem = driver.find_element(By.ID, "wd")
                    search_input_elem.clear()
                    search_input_elem.send_keys(word)

                    select = Select(driver.find_element(By.ID, "sort"))
                    select.select_by_value(style_value)

                    submit_button = driver.find_element(By.XPATH, "//form[@name='form1']//button[@type='submit']")
                    submit_button.click()
                    time.sleep(random.uniform(2, 3))

                    j_elements = driver.find_elements(By.CSS_SELECTOR, "div.j")
                    if not filter_calligrapher_list:
                        j_elements = j_elements[1:]

                    for j in j_elements[:-1]:
                        try:
                            a_img = j.find_element(By.CSS_SELECTOR, "div.mbpho a")
                            img_url = a_img.get_attribute("href")
                        except:
                            continue

                        try:
                            g_div = j.find_element(By.CSS_SELECTOR, "div.g")
                            a_btnsfj = g_div.find_element(By.CSS_SELECTOR, "a.btnSFJ")
                            author_name = a_btnsfj.get_attribute("sfj") or a_btnsfj.text.strip()
                        except:
                            author_name = g_div.text.split('\n')[0].strip()

                        if filter_calligrapher_list and (convert(author_name,'zh-tw') not in filter_calligrapher_list):
                            continue

                        results.append((word, author_name, img_url))
                        word_found = True

                    if not word_found:
                        if not any(r[0] == word and r[1] == "查無此字" for r in results):
                            results.append((word, "查無此字", None))

                except Exception as e:
                    results.append((word, "查無此字", None))
                    st.warning(f"{word} 搜尋失敗: {e}")

                completed = idx + 1
                elapsed = time.time() - start_time
                avg_time = elapsed / completed
                remaining = (total_words - completed) * avg_time
                remain_min = int(remaining // 60)
                remain_sec = int(remaining % 60)

                progress_bar.progress(completed / total_words)
                status_text.text(
                    f"正在搜尋第 {completed}/{total_words} 個字：{word} ⏳ 預估剩餘 {remain_min}分{remain_sec}秒"
                )

        finally:
            if driver:
                driver.quit()

        # 如果整體沒有任何圖片，給 placeholder
        has_any_image = any(img_url for _, _, img_url in results)
        if not has_any_image:
            results = [(word, "查無此字", placeholder_img_path) for word in search_words]

        st.session_state.results = results

        # 初始化 display_index，字+instance_id
        word_count = defaultdict(int)
        for word in search_words:
            word_count[word] += 1
            instance_id = word_count[word]
            st.session_state.display_index[f"{word}_{instance_id}"] = 0

# ================= 顯示搜尋結果 & 下一批圖片功能 =================
results = st.session_state.get("results", [])
if results:
    search_words = list(search_input_chinese.strip())
    groups_dict = defaultdict(list)
    for word, author, img_url in results:
        groups_dict[word].append((word, author, img_url))

    word_count = defaultdict(int)
    for w_idx, w in enumerate(search_words):
        word_count[w] += 1
        instance_id = word_count[w]
        group_items = groups_dict.get(w, [])
        if not group_items:
            continue

        st.subheader(f"🔍 {w} ({style_dict[style_value]})")
        start = st.session_state.display_index.get(f"{w}_{instance_id}", 0)
        end = min(start + download_limit, len(group_items))
        batch_items = group_items[start:end]

        # 確保每個 batch 至少有一張圖片
        img_urls = [img_url if img_url else placeholder_img_path for _, _, img_url in batch_items]
        labels = [convert(author,'zh-tw') if img_url else "查無此字" for _, author, img_url in batch_items]

        selected_idx = image_select(
            label=f"選擇 {w} 的圖片",
            images=img_urls,
            captions=labels,
            return_value="index",
            key=f"img_select_{w}_{instance_id}_{start}"
        )

        # 限制每組只能選一張圖片
        st.session_state.selected_images = [
            x for x in st.session_state.selected_images if x[1] != f"{w}_{instance_id}"
        ]
        if selected_idx is not None:
            word_sel, author_name, img_url = batch_items[selected_idx]
            st.session_state.selected_images.append((w_idx, f"{w}_{instance_id}", author_name, img_url))

        # 下一批按鈕
        if end < len(group_items):
            if st.button(f"下一批 {w}", key=f"next_batch_{w}_{instance_id}"):
                st.session_state.display_index[f"{w}_{instance_id}"] = start + download_limit

# ================= 顯示挑選圖片 =================
if st.session_state.selected_images:
    st.subheader("✅ 你挑選的圖片（列水平排列，列內直向堆疊）")
    sorted_selected = sorted(st.session_state.selected_images, key=lambda x: x[0])
    max_per_column = st.slider("一行最多顯示幾個字", 1, 10, 3)

    columns_data = [sorted_selected[i:i + max_per_column] for i in range(0, len(sorted_selected), max_per_column)]
    columns_data = columns_data[::-1]
    cols = st.columns(len(columns_data))
    for col, batch in zip(cols, columns_data):
        with col:
            for _, word, author, img_url in batch:
                safe_show_image(img_url, width=60)

    buffer = download_word(st.session_state.selected_images)
    st.download_button(
        label="📥 下載 Word",
        data=buffer,
        file_name="selected_images.docx",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
