import streamlit as st
import json
import random
import io
from datetime import datetime
import pandas as pd

# --- 1. 狀態初始化 ---
# 初始化所有必要的狀態變數，確保程式碼重新運行時資料不會丟失
def init_session_state():
    if 'questions' not in st.session_state:
        st.session_state.questions = []
    if 'all_questions' not in st.session_state:
        st.session_state.all_questions = []
    if 'current_index' not in st.session_state:
        st.session_state.current_index = 0
    if 'answers' not in st.session_state:
        st.session_state.answers = {}
    if 'quiz_started' not in st.session_state:
        st.session_state.quiz_started = False
    if 'quiz_finished' not in st.session_state:
        st.session_state.quiz_finished = False
    if 'font_size' not in st.session_state:
        st.session_state.font_size = 20
    if 'errors' not in st.session_state:
        st.session_state.errors = []

init_session_state()

# --- 2. 核心邏輯 (功能函數化) ---

def load_files(uploaded_files):
    """從上傳的檔案中加載所有題目，並更新狀態"""
    all_qs = []
    for file in uploaded_files:
        try:
            # 檔案內容是 bytes，需要解碼
            file_content = file.read().decode('utf-8')
            all_qs.extend(json.loads(file_content))
        except Exception as e:
            st.error(f"檔案 {file.name} 載入失敗或格式錯誤: {e}")
            return
    st.session_state.all_questions = all_qs
    st.toast(f"成功載入 {len(all_qs)} 題。")

def start_quiz(num_single, num_multi):
    """開始測驗，處理抽題和選項亂序邏輯"""
    all_qs = st.session_state.all_questions
    if not all_qs:
        st.error("請先上傳題庫 JSON 檔案。")
        return

    try:
        num_single = int(num_single)
        num_multi = int(num_multi)
    except ValueError:
        st.error("請輸入正確的題數")
        return

    single_qs = [q for q in all_qs if q.get('type') == 'single']
    multi_qs = [q for q in all_qs if q.get('type') == 'multi']

    if num_single > len(single_qs) or num_multi > len(multi_qs):
        st.error(f"題庫數量不足。單選需 {num_single} 題 (庫存 {len(single_qs)})，多選需 {num_multi} 題 (庫存 {len(multi_qs)})。")
        return

    # 抽題並洗牌
    selected_questions = random.sample(single_qs, num_single) + random.sample(multi_qs, num_multi)
    random.shuffle(selected_questions)

    # 對每一題進行選項亂序（並同步更新正解索引）
    for q in selected_questions:
        original_options = q["options"]
        original_answers = q["answer"]  # 1-based list

        # 將原始 options 與 index 綁在一起並打亂
        option_with_index = list(enumerate(original_options))
        random.shuffle(option_with_index)

        # 建立新 options 與新的正解索引（1-based）
        shuffled_options = []
        new_answer_indices = []

        for new_index, (old_index, opt_text) in enumerate(option_with_index):
            shuffled_options.append(opt_text)
            if (old_index + 1) in original_answers:  # 原本正解是第 old_index+1 項
                new_answer_indices.append(new_index + 1)  # 新的 1-based index

        q["options"] = shuffled_options
        q["answer"] = sorted(new_answer_indices)

    # 更新狀態
    st.session_state.questions = selected_questions
    st.session_state.answers = {}
    st.session_state.current_index = 0
    st.session_state.quiz_started = True
    st.session_state.quiz_finished = False
    st.rerun() # 重新運行以切換到測驗畫面

def save_answer(question_index, selected_options):
    """儲存當前題目的答案"""
    # selected_options 來自介面，是 1-based index 列表
    st.session_state.answers[question_index] = selected_options

def navigate_question(direction):
    """處理上一題/下一題的切換"""
    q = st.session_state.questions[st.session_state.current_index]
    
    # 儲存當前答案 (這裡我們假設選項組件已經更新了 session state)
    # Streamlit 會自動處理按鈕觸發前的所有輸入框/選項狀態
    
    # 手動保存當前選項的邏輯（如果使用 checkbox / radio groups，不需要手動讀取 var_list）
    # 因為我們將選項的 state key 設為 'q_answer_X'，所以 Streamlit 已經在記憶中。

    # 必須手動保存當前題目的答案 (這步是將當前頁面的答案存入 answers 字典)
    # 答案會從 show_question 裡的 component 拿到
    current_answer_key = f'q_answer_{st.session_state.current_index}'
    if current_answer_key in st.session_state:
        # Streamlit Radio button 回傳單個值 (single)，Checkbox group 回傳列表 (multi)
        current_answer = st.session_state[current_answer_key]
        if q['type'] == 'single' and current_answer:
            # 單選：確保是列表 [1, 2, 3...]
            st.session_state.answers[st.session_state.current_index] = [current_answer]
        elif q['type'] == 'multi' and current_answer:
            # 多選：確保是列表 [1, 2, 3...]
            st.session_state.answers[st.session_state.current_index] = [int(a.split(')')[0]) for a in current_answer]
        else:
             st.session_state.answers[st.session_state.current_index] = [] # 未選

    if direction == "prev" and st.session_state.current_index > 0:
        st.session_state.current_index -= 1
    elif direction == "next" and st.session_state.current_index < len(st.session_state.questions) - 1:
        st.session_state.current_index += 1
    elif direction == "finish":
        finish_quiz()
        return

    st.rerun() # 切換頁面

def finish_quiz():
    """計算並顯示結果，準備錯題匯出資料"""
    score = 0
    total = len(st.session_state.questions)
    st.session_state.errors = []
    
    # 確保最後一題的答案被保存
    current_answer_key = f'q_answer_{st.session_state.current_index}'
    q = st.session_state.questions[st.session_state.current_index]
    if current_answer_key in st.session_state:
        current_answer = st.session_state[current_answer_key]
        if q['type'] == 'single' and current_answer:
            st.session_state.answers[st.session_state.current_index] = [current_answer]
        elif q['type'] == 'multi' and current_answer:
            st.session_state.answers[st.session_state.current_index] = [int(a.split(')')[0]) for a in current_answer]
        else:
             st.session_state.answers[st.session_state.current_index] = []

    for i, q in enumerate(st.session_state.questions):
        correct = sorted(q['answer'])
        selected = sorted(st.session_state.answers.get(i, []))
        
        # Streamlit 的選項回傳是字串，需要轉換回 1-based 索引進行比較
        
        if correct == selected:
            score += 1
        else:
            q_copy = q.copy()
            q_copy['selected'] = selected
            st.session_state.errors.append(q_copy)

    percent = round(score / total * 100, 2)
    st.session_state.score = score
    st.session_state.total = total
    st.session_state.percent = percent
    st.session_state.quiz_finished = True
    st.session_state.quiz_started = False
    st.rerun() # 切換到結果頁面

def reset_quiz():
    """重設測驗狀態"""
    st.session_state.questions = []
    st.session_state.current_index = 0
    st.session_state.answers = {}
    st.session_state.quiz_started = False
    st.session_state.quiz_finished = False
    st.rerun()
    
# --- 3. 網頁介面顯示函數 ---

def show_settings_page():
    """顯示設定和檔案上傳介面"""
    st.header("⚙️ 測驗系統設置與題庫加載")

    # 檔案上傳 (取代 filedialog)
    st.markdown("---")
    uploaded_files = st.file_uploader(
        "請選擇題庫 JSON 檔案 (可複選，需符合原格式)",
        type="json",
        accept_multiple_files=True,
        on_change=lambda: load_files(st.session_state['uploader']) # 使用 on_change 確保狀態更新
        ,key='uploader'
    )
    
    if st.session_state.all_questions:
        st.info(f"當前已載入 **{len(st.session_state.all_questions)}** 題。")
    
    # 題數設定
    st.subheader("抽題設定")
    
    col1, col2 = st.columns(2)
    with col1:
        num_single = st.text_input("單選題數 (Single-Choice):", value="5")
    with col2:
        num_multi = st.text_input("多選題數 (Multi-Choice):", value="2")

    # 字體大小設定 (直接修改 CSS variable)
    st.subheader("顯示設定")
    
    # Streamlit 的 input 總是回傳字串，需要轉換
    new_font_size = st.slider("字體大小 (用於選項及題目)", min_value=12, max_value=30, value=st.session_state.font_size, step=1, key='font_slider')
    st.session_state.font_size = new_font_size
    
    # 由於 Streamlit 無法像 Tkinter 那樣直接控制所有元件字體，我們用 CSS 注入
    st.markdown(
        f"""
        <style>
        .stButton>button, .stTextInput>div>div>input, .stSelectbox>div, .stRadio>div, .stCheckbox>label {{
            font-size: {st.session_state.font_size}px;
        }}
        .stMarkdown h3, .stMarkdown h2 {{
            font-size: {st.session_state.font_size + 4}px;
        }}
        </style>
        """,
        unsafe_allow_html=True
    )

    # 開始按鈕
    st.markdown("---")
    if st.button("🚀 開始測驗", type="primary", use_container_width=True):
        if not st.session_state.all_questions:
            st.error("請先上傳題庫！")
        else:
            start_quiz(num_single, num_multi)

def show_quiz_page():
    """顯示單一題目與選項介面"""
    q_index = st.session_state.current_index
    q = st.session_state.questions[q_index]
    total_q = len(st.session_state.questions)
    
    # 顯示題目
    q_type = "【單選】" if q.get('type') == 'single' else "【多選】"
    st.subheader(f"第 {q_index + 1}/{total_q} 題 {q_type}：")
    st.markdown(f"**{q.get('question')}**")

    # 取得歷史答案 (1-based index)
    prev_selected_indices = st.session_state.answers.get(q_index, [])
    
    # 將選項轉換為帶有 (1), (2) 標記的字串列表
    option_labels = [f"({i+1}) {opt}" for i, opt in enumerate(q['options'])]
    
    # 預設選中的選項，用於介面初始化
    default_selection = []
    if prev_selected_indices:
        # 將 1-based index 轉換回 option_labels 列表中的元素
        default_selection = [option_labels[idx-1] for idx in prev_selected_indices if 0 < idx <= len(option_labels)]

    # 選項元件
    # 每個選項組件都使用唯一的 key，並將答案直接儲存到 session state 中
    component_key = f'q_answer_{q_index}'
    
    if q['type'] == 'single':
        # 單選題：使用 Radio Button，回傳單個選項文字
        # 這裡的 default value 必須是 option_labels 中的一個元素，如果沒有選擇，則為 None
        selected_label = st.radio(
            "請選擇一個答案：",
            options=option_labels,
            index=option_labels.index(default_selection[0]) if default_selection else None,
            key=component_key
        )
        # 由於 Radio button 返回的是 label 字串，我們需要將它轉換為 1-based index
        if selected_label:
            selected_index = int(selected_label.split(')')[0])
            st.session_state.answers[q_index] = [selected_index]

    else:
        # 多選題：使用 Checkbox Group，回傳選中選項文字的列表
        # Streamlit 的 multiselect 適合多選，但 Checkbox Group 視覺上更像原本的 App
        selected_labels = st.multiselect(
            "請選擇所有正確答案：",
            options=option_labels,
            default=default_selection,
            key=component_key
        )
        # 將選中的 label 字串列表轉換為 1-based index 列表
        if selected_labels:
            selected_indices = [int(label.split(')')[0]) for label in selected_labels]
            st.session_state.answers[q_index] = selected_indices
        else:
            st.session_state.answers[q_index] = []

    # 導航按鈕
    st.markdown("---")
    col_nav = st.columns(3)
    
    # 上一題
    with col_nav[0]:
        if st.session_state.current_index > 0:
            st.button("⬅️ 上一題", on_click=navigate_question, args=("prev",), use_container_width=True)
        else:
            st.button("🚫 上一題 (首頁)", disabled=True, use_container_width=True)

    # 進度顯示
    with col_nav[1]:
        st.markdown(f"<p style='text-align: center; font-weight: bold;'>{q_index + 1}/{total_q}</p>", unsafe_allow_html=True)
    
    # 下一題/完成
    with col_nav[2]:
        if st.session_state.current_index < total_q - 1:
            st.button("下一題 ➡️", on_click=navigate_question, args=("next",), type="secondary", use_container_width=True)
        else:
            st.button("✅ 完成測驗", on_click=navigate_question, args=("finish",), type="primary", use_container_width=True)
            
    # 顯示目前已選答案（方便調試）
    # st.sidebar.write("當前答案:", st.session_state.answers.get(q_index, []))


def show_result_page():
    """顯示測驗結果並提供錯題下載"""
    
    st.balloons()
    st.header("🎉 測驗完成！")
    
    # 總分卡片
    st.metric(
        label="總體成績",
        value=f"{st.session_state.percent}%",
        delta=f"答對 {st.session_state.score} / {st.session_state.total} 題"
    )

    if st.session_state.errors:
        st.subheader("📚 錯題分析")
        st.warning(f"您答錯了 {len(st.session_state.errors)} 題，請下載錯題檔案進行複習。")

        # 準備錯題 JSON 數據
        errors_json = json.dumps(
            st.session_state.errors,
            ensure_ascii=False,
            indent=2
        ).encode('utf-8')
        
        # 錯題下載 (取代 filedialog.askdirectory)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"錯題報告_{timestamp}.json"
        
        st.download_button(
            label="⬇️ 下載錯誤題目 JSON 檔案",
            data=errors_json,
            file_name=filename,
            mime="application/json",
            type="secondary",
            use_container_width=True
        )
        
        # 顯示錯題概覽 (可選)
        with st.expander("查看所有錯題的題目名稱"):
            for i, error_q in enumerate(st.session_state.errors):
                st.markdown(f"**{i+1}.** {error_q.get('question')[:50]}...")
            
    else:
        st.success("恭喜您！所有題目都答對了！")

    st.markdown("---")
    if st.button("🔙 回到設定首頁", type="primary"):
        reset_quiz()

# --- 4. 主程式流程控制 ---

st.title("📱 跨平台題庫測驗系統 (Web App)")

if st.session_state.quiz_started:
    show_quiz_page()
elif st.session_state.quiz_finished:
    show_result_page()
else:
    show_settings_page()

# 頁腳，讓使用者知道如何開始
if not st.session_state.quiz_started and not st.session_state.quiz_finished:
    st.sidebar.markdown("---")
    st.sidebar.caption("使用說明：")
    st.sidebar.markdown(
        """
        1.  點擊 **「選擇檔案」** 上傳您的題庫 JSON 檔。
        2.  設定單選和多選的抽題數量。
        3.  點擊 **「開始測驗」**。
        4.  在您的 **iOS 裝置上**，打開這個網頁，並使用 Safari 的 **「加入主畫面」** 功能，即可像 App 一樣運行。
        """
    )