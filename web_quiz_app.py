import streamlit as st
import json
import random
from datetime import datetime
import io

# 設定 Streamlit 頁面基礎配置
st.set_page_config(page_title="跨平台題庫測驗", layout="centered")

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
        st.session_state.answers = {} # 儲存 {題號: [答案索引 (1-based)]}
    if 'quiz_started' not in st.session_state:
        st.session_state.quiz_started = False
    if 'quiz_finished' not in st.session_state:
        st.session_state.quiz_finished = False
    if 'font_size' not in st.session_state:
        st.session_state.font_size = 20
    if 'errors' not in st.session_state:
        st.session_state.errors = []
    # 儲存當前上傳的檔案物件，用於判斷是否需要重新載入
    if 'uploaded_file_names' not in st.session_state:
        st.session_state.uploaded_file_names = []

init_session_state()

# --- 2. 核心邏輯 (功能函數化) ---

def load_files(uploaded_files):
    """從上傳的檔案中加載所有題目，並更新狀態"""
    all_qs = []
    current_file_names = []

    for file in uploaded_files:
        try:
            # 檔案內容是 bytes，需要解碼
            file_content = file.read().decode('utf-8')
            all_qs.extend(json.loads(file_content))
            current_file_names.append(file.name)
        except Exception as e:
            st.error(f"檔案 {file.name} 載入失敗或格式錯誤: {e}")
            return
            
    # 更新狀態
    st.session_state.all_questions = all_qs
    st.session_state.uploaded_file_names = current_file_names
    st.info(f"成功載入 **{len(all_qs)}** 題。 (來自: {', '.join(current_file_names)})")

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
        option_with_index = list(enumerate(original_options)) # 0-based index
        random.shuffle(option_with_index)

        # 建立新 options 與新的正解索引（1-based）
        shuffled_options = []
        new_answer_indices = []

        for new_index, (old_index, opt_text) in enumerate(option_with_index):
            shuffled_options.append(opt_text)
            # 檢查原始答案是否包含 old_index + 1 (即 1-based index)
            if (old_index + 1) in original_answers:  
                new_answer_indices.append(new_index + 1) # 新的 1-based index

        q["options"] = shuffled_options
        q["answer"] = sorted(new_answer_indices)

    # 更新狀態
    st.session_state.questions = selected_questions
    st.session_state.answers = {}
    st.session_state.current_index = 0
    st.session_state.quiz_started = True
    st.session_state.quiz_finished = False
    st.rerun() # 重新運行以切換到測驗畫面

def save_current_answer():
    """
    保存當前頁面的答案到 st.session_state.answers 字典中。
    在導航或結束測驗前調用。
    Streamlit Radio Button 回傳選項標籤字串，Multiselect 回傳選項標籤字串列表。
    """
    q_index = st.session_state.current_index
    q = st.session_state.questions[q_index]
    component_key = f'q_answer_{q_index}'

    current_answer = st.session_state.get(component_key)
    
    selected_indices = []
    
    if current_answer is None or (isinstance(current_answer, list) and not current_answer):
        # 無選擇答案 (Radio None, Multiselect [])
        st.session_state.answers[q_index] = selected_indices # 存儲空列表
        return
        
    if q['type'] == 'single':
        # 單選：Streamlit Radio Button 回傳單個選項標籤 (e.g., '(1) Option A')
        if isinstance(current_answer, str):
            try:
                # 提取 (1) 中的數字，例如 '(1) Option A' -> '1' -> 1 (1-based index)
                index_str = current_answer.split(')')[0].strip('(')
                index = int(index_str) 
                selected_indices = [index]
            except ValueError:
                selected_indices = []
                
    elif q['type'] == 'multi':
        # 多選：Streamlit Multiselect 回傳選項標籤的列表
        if isinstance(current_answer, list):
            # 從標籤列表中解析出 1-based index 列表
            for label in current_answer:
                try:
                    # 提取 (1) 中的數字
                    index_str = label.split(')')[0].strip('(')
                    index = int(index_str)
                    selected_indices.append(index)
                except ValueError:
                    continue
    
    st.session_state.answers[q_index] = sorted(selected_indices)

def navigate_question(direction):
    """處理上一題/下一題的切換"""
    # 1. 儲存當前答案
    save_current_answer()

    # 2. 導航
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
    # 確保最後一題的答案被保存
    save_current_answer()
    
    score = 0
    total = len(st.session_state.questions)
    st.session_state.errors = []
    
    for i, q in enumerate(st.session_state.questions):
        correct = sorted(q['answer']) # 1-based index
        selected = st.session_state.answers.get(i, []) # 1-based index

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
    st.session_state.all_questions = []
    # 重設 uploader widget，讓用戶可以重新上傳
    st.session_state.uploader = []
    st.session_state.uploaded_file_names = []
    st.rerun()
    
# --- 3. 網頁介面顯示函數 ---

def show_settings_page():
    """顯示設定和檔案上傳介面"""
    st.header("⚙️ 測驗系統設置與題庫加載")

    # 檔案上傳
    st.markdown("---")
    uploaded_files = st.file_uploader(
        "請選擇題庫 JSON 檔案 (可複選，需符合原格式)",
        type="json",
        accept_multiple_files=True,
        key='uploader'
    )
    
    # 處理檔案上傳的優化邏輯：檢查當前上傳的檔案數量或名稱是否與已載入的匹配，若否則重新載入
    current_names = [f.name for f in uploaded_files] if uploaded_files else []
    
    if uploaded_files and (current_names != st.session_state.uploaded_file_names or len(st.session_state.all_questions) == 0):
        # 僅在檔案名稱列表不匹配或題庫為空時才觸發 load_files
        load_files(uploaded_files)

    if st.session_state.all_questions:
        st.success(f"當前已載入 **{len(st.session_state.all_questions)}** 題。")
    
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
    
    # 由於 Streamlit 無法直接控制所有元件字體，我們用 CSS 注入
    st.markdown(
        f"""
        <style>
        /* 應用於按鈕、輸入框、選項文字等 */
        .stButton>button, .stTextInput>div>div>input, .stSelectbox>div, .stRadio>div, .stCheckbox>label, .stMultiSelect>div {{
            font-size: {st.session_state.font_size}px;
        }}
        /* 應用於題目等標題 */
        .stMarkdown h3, .stMarkdown h2, .stMarkdown p, .stMarkdown strong {{
            font-size: {st.session_state.font_size + 2}px;
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
    
    # 預設選中的選項標籤，用於介面初始化
    default_selection_labels = []
    if prev_selected_indices:
        # 將 1-based index 轉換回 option_labels 列表中的元素
        for idx in prev_selected_indices:
             # 確保索引在有效範圍內
             if 0 < idx <= len(option_labels):
                 default_selection_labels.append(option_labels[idx - 1])

    # 選項元件 key
    component_key = f'q_answer_{q_index}'
    
    if q['type'] == 'single':
        # 單選題：使用 Radio Button
        default_index = -1
        if default_selection_labels:
            try:
                # 找到預設選項在 options 列表中的 0-based index
                default_index = option_labels.index(default_selection_labels[0])
            except ValueError:
                default_index = -1
        
        # 設置 index=None，讓 Streamlit 在沒有選擇時返回 None
        st.radio(
            "請選擇一個答案：",
            options=option_labels,
            index=default_index if default_index >= 0 else None,
            key=component_key
        )
    else:
        # 多選題：使用 Multiselect
        st.multiselect(
            "請選擇所有正確答案：",
            options=option_labels,
            default=default_selection_labels,
            key=component_key
        )

    # 導航按鈕
    st.markdown("---")
    col_nav = st.columns(3)
    
    # 上一題
    with col_nav[0]:
        if st.session_state.current_index > 0:
            # 使用 on_click 確保點擊時觸發 navigate_question
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


def show_result_page():
    """顯示測驗結果並提供錯題下載"""
    
    if st.session_state.percent >= 80:
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
        # 為了匯出方便，將答案從 1-based index 轉回選項文字
        errors_for_export = []
        for err in st.session_state.errors:
            export_q = err.copy()
            # 將 selected 1-based index 轉換為選項文字列表
            selected_labels = [export_q['options'][idx - 1] for idx in export_q.get('selected', []) if idx > 0 and idx <= len(export_q['options'])]
            
            # 將正確答案 1-based index 轉換為選項文字列表
            correct_labels = [export_q['options'][idx - 1] for idx in export_q.get('answer', []) if idx > 0 and idx <= len(export_q['options'])]
            
            export_q['您的選擇'] = selected_labels
            export_q['正確答案'] = correct_labels
            # 移除用於計算的數字 index
            del export_q['answer']
            if 'selected' in export_q:
                del export_q['selected']
            
            errors_for_export.append(export_q)


        errors_json = json.dumps(
            errors_for_export,
            ensure_ascii=False,
            indent=2
        ).encode('utf-8')
        
        # 錯題下載
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
        
        # 顯示錯題概覽
        with st.expander("📝 展開查看所有錯題的詳細報告"):
            for i, error_q in enumerate(errors_for_export):
                # 重新組合選項為 (1) Option A, (2) Option B...
                options_str = "\n".join([f"({j+1}) {opt}" for j, opt in enumerate(error_q.get('options', []))])
                
                st.markdown(f"#### 錯誤題目 {i+1}. {error_q.get('question')}")
                st.markdown(f"**所有選項:**\n{options_str}")
                st.markdown(f"**您的答案:** {', '.join(error_q.get('您的選擇', ['無']))}")
                st.markdown(f"**正確答案:** {', '.join(error_q.get('正確答案', ['無']))}")
                st.markdown("---")
            
    else:
        st.success("恭喜您！所有題目都答對了！")

    st.markdown("---")
    if st.button("🔙 回到設定首頁", type="primary"):
        reset_quiz()

# --- 4. 主程式流程控制 ---

st.title("📱 跨平台題庫測驗系統 (Web App)")
st.caption("適用於電腦、Android 及 iOS (可加入主畫面)")

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
        2.  設定抽題數量與字體大小。
        3.  點擊 **「開始測驗」**。
        4.  在您的 **iOS 裝置上**，使用 Safari 開啟此網頁並 **「加入主畫面」**，即可獲得 App 體驗。
        """
    )
