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

# ========== 初始化 session_state ==========
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

# ========== 搜尋按鈕 ==========
if st.button("開始搜尋"):
    st.session_state.results = []
    st.session_state.selected_images = []
    st.session_state.display_index = {}

    search_words = list(search_input_chinese.strip())
    results = []
    progress_bar = st.progress(0, text = '搜尋中，請稍後')
    status_text = st.empty()
    total_words = len(search_words)

    # ========== Selenium 設定 ==========
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--incognito")
    options.add_argument("--disable-dev-shm-usage")  # container safe
    service = Service(ChromeDriverManager(chrome_type=ChromeType.CHROMIUM).install())
    driver = webdriver.Chrome(service=service, options=options)

    driver = None
    try:  # #️⃣ 使用 try/finally 確保 driver 會被關閉
        driver = webdriver.Chrome(service=service, options=options)
        base_url = "https://www.shufazidian.com/s.php"

        for idx, word in enumerate(search_words):
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

                # 初始化計時
                start_time = time.time()

                for idx, word in enumerate(search_words):
                    driver.get(base_url)
                    time.sleep(random.uniform(1, 2))
                    ...
                    submit_button.click()
                    time.sleep(random.uniform(2, 3))

                    # 已完成數量
                    completed = idx + 1
                    elapsed = time.time() - start_time
                    avg_time = elapsed / completed
                    remaining = (total_words - completed) * avg_time

                    # 轉換時間格式
                    remain_min = int(remaining // 60)
                    remain_sec = int(remaining % 60)

                    progress_bar.progress(completed / total_words)
                    status_text.text(
                        f"正在搜尋第 {completed}/{total_words} 個字：{word} ⏳ 預估剩餘 {remain_min}分{remain_sec}秒"
                    )

                j_elements = driver.find_elements(By.CSS_SELECTOR, "div.j")
                if not filter_calligrapher_list:
                    j_elements = j_elements[1:]

                word_found = False
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

                # 如果沒找到，就加 placeholder
                if not word_found:
                    results.append((word, "查無此字", placeholder_img_path))

            except Exception as e:
                # #️⃣ 單個字出錯時，也不影響整體流程
                results.append((word, "查無此字", placeholder_img_path))
                st.warning(f"{word} 搜尋失敗: {e}")

    finally:
        if driver:
            driver.quit()  # #️⃣ 確保 driver 一定關閉

    st.session_state.results = results

    # 初始化 display_index
    for word in search_words:
        st.session_state.display_index[word] = 0

# ========== 顯示搜尋結果 & 收藏圖片邏輯 ==========
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

    for w_idx, w in enumerate(search_words):
        group_items = groups_dict.get(w, [])
        if not group_items:
            continue

        st.subheader(f"🔍 {w} ({style_dict[style_value]})")

        start = st.session_state.display_index.get(w, 0)
        end = min(start + download_limit, len(group_items))
        batch_items = group_items[start:end]

        img_urls = [img_url for _, _, img_url in batch_items]
        labels = [f"{convert(author, 'zh-tw')}" for _, author, _ in batch_items]

        selected_idx = image_select(
            label=f"選擇 {w} 的圖片",
            images=img_urls,
            captions=labels,
            return_value="index",
            key=f"img_select_{w_idx}_{start}",
            use_container_width=False,
        )

        st.session_state.selected_images = [x for x in st.session_state.selected_images if x[1] != w]
        if selected_idx is not None:
            word, author_name, img_url = batch_items[selected_idx]
            st.session_state.selected_images.append((w_idx, word, author_name, img_url))

        next_batch_key = f"next_batch_{w_idx}_{w}"
        if end < len(group_items):
            if st.button(f"下一批 {w}", key=next_batch_key):
                st.session_state.display_index[w] = start + download_limit
                st.session_state.selected_images = [x for x in st.session_state.selected_images if x[1] != w]

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
