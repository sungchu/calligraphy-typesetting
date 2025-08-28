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

# ================= 初始化 session_state =================
if "results" not in st.session_state:
    st.session_state.results = []
if "selected_images" not in st.session_state:
    st.session_state.selected_images = []
if "display_index" not in st.session_state:
    st.session_state.display_index = {}

st.title("書法字典圖片瀏覽器")

search_input = st.text_input("輸入要搜尋的文字（可多個字，無空格）")
search_input_chinese = "".join(re.findall(r"[\u4e00-\u9fff]+", search_input))
style_dict = {"1": "章草", "3": "篆書", "4": "簡牘", "5": "魏碑",
              "6": "隸書", "7": "草書", "8": "行書", "9": "楷書"}
style_value = st.selectbox("選擇書法字體",
                           options=list(style_dict.keys()),
                           format_func=lambda x: style_dict[x],
                           index=7)

filter_calligrapher_input = st.text_input(
    "指定特定書法家（若有多位，請用、分隔，留空則代表不指定）", ""
)
if filter_calligrapher_input.strip():
    filter_calligrapher_list = [c.strip() for c in filter_calligrapher_input.split("、") if c.strip()]
else:
    filter_calligrapher_list = None

download_limit = 4
placeholder_img_path = os.path.join(os.getcwd(), "查無此字.png")  # 同資料夾下

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

# ================= 顯示搜尋結果 & 下一批圖片功能 =================
results = st.session_state.get("results", [])
if results:
    search_words = list(search_input_chinese.strip())
    groups_dict = defaultdict(list)
    for word, author, img_url in results:
        groups_dict[word].append((word, author, img_url))

    st.markdown(
        """
        <style>
        .stImage img {
            max-width: 120px !important;
            height: auto !important;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    word_count = defaultdict(int)
    for w_idx, w in enumerate(search_words):
        word_count[w] += 1
        instance_id = word_count[w]
        group_items = groups_dict.get(w, [])
        if not group_items:
            continue

        st.subheader(f"🔍 {w} ({style_dict[style_value]})")

        idx_key = f"{w}_{instance_id}"
        if idx_key not in st.session_state.display_index:
            st.session_state.display_index[idx_key] = 0

        start = st.session_state.display_index[idx_key]
        end = min(start + download_limit, len(group_items))
        batch_items = group_items[start:end]

        img_urls = [img_url if img_url else placeholder_img_path for _, _, img_url in batch_items]
        labels = [convert(author,'zh-tw') if img_url else "查無此字" for _, author, img_url in batch_items]

        widget_key = f"img_select_{w}_{instance_id}_{start}"
        selected_idx = image_select(
            label=f"選擇 {w} 的圖片",
            images=img_urls,
            captions=labels,
            return_value="index",
            key=widget_key
        )

        # 限制每組只能選一張圖片
        st.session_state.selected_images = [
            x for x in st.session_state.selected_images if x[1] != idx_key
        ]
        if selected_idx is not None:
            word_sel, author_name, img_url = batch_items[selected_idx]
            st.session_state.selected_images.append((w_idx, idx_key, author_name, img_url))

        # 下一批按鈕
        if end < len(group_items):
            next_key = f"next_batch_{w}_{instance_id}"
            if st.button(f"下一批 {w}", key=next_key):
                st.session_state.display_index[idx_key] += download_limit
                # Streamlit 自動 rerun，不需 experimental_rerun

# ================= 顯示挑選圖片 =================
if st.session_state.selected_images:
    st.subheader("✅ 你挑選的圖片（列水平排列，列內直向堆疊）")
    sorted_selected = sorted(st.session_state.selected_images, key=lambda x: x[0])
    max_per_column = st.slider("每列最多顯示幾張圖片（垂直堆疊）", 1, 10, 3)

    columns_data = [sorted_selected[i:i + max_per_column] for i in range(0, len(sorted_selected), max_per_column)]
    columns_data = columns_data[::-1]
    cols = st.columns(len(columns_data))
    for col, batch in zip(cols, columns_data):
        with col:
            for _, word, author, img_url in batch:
                st.image(img_url, width=120)
