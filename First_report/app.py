# streamlit run app.py

import streamlit as st
from llama_index.core.llms import ChatMessage
from llama_index.core.memory import ChatMemoryBuffer
from llama_index.llms.ollama import Ollama
import pandas as pd, os, time, logging

logging.basicConfig(level=logging.INFO)
CSV_PATH = "feedback_log.csv"

# 세션 초기화
if "messages" not in st.session_state:
    st.session_state.messages = []
if "memory" not in st.session_state:
    st.session_state.memory = ChatMemoryBuffer.from_defaults(token_limit=2048)
if "feedback_states" not in st.session_state:
    st.session_state.feedback_states = {}
if "just_saved" not in st.session_state:
    st.session_state.just_saved = None  # 마지막으로 피드백 저장된 답변 번호

# CSV 파일 준비
if not os.path.exists(CSV_PATH):
    pd.DataFrame(columns=["질문", "별점", "피드백", "인공지능 답변"]).to_csv(CSV_PATH, index=False)

def append_feedback(rating, fb, question, answer):
    """질문 포함해서 피드백 저장"""

    # 좌우 공백 제거
    try:
        fb = str(fb).strip() 
    except:
        pass

    df = pd.DataFrame([{
        "질문": question,
        "별점": rating,
        "피드백": fb,
        "인공지능 답변": answer
    }])
    df.to_csv(CSV_PATH, mode="a", header=False, index=False)

def stream_chat(model, messages):
    llm = Ollama(model=model, request_timeout=180.0)
    resp = llm.stream_chat(messages)
    response, placeholder = "", st.empty()
    for r in resp:
        response += r.delta
        placeholder.write(response)
    return response

def main():
    st.title("LLM-Chatbot by EXAONE")
    model = st.sidebar.selectbox("모델 선택", ["exaone3.5:2.4b"])

    if st.sidebar.button("초기화"):
        st.session_state.messages = []
        st.session_state.memory = ChatMemoryBuffer.from_defaults(token_limit=2048)
        st.session_state.feedback_states = {}
        st.session_state.just_saved = None
        st.success("모든 대화 및 피드백이 초기화되었습니다.")

    # === 대화 렌더링 ===
    answer_idx = 0
    for i, msg in enumerate(st.session_state.messages):
        with st.chat_message(msg["role"]):
            st.write(msg["content"])
            if msg["role"] == "assistant":
                answer_idx += 1
                if answer_idx not in st.session_state.feedback_states:
                    st.session_state.feedback_states[answer_idx] = {
                        "rating": None, "feedback": "", "done": False
                    }
                fs = st.session_state.feedback_states[answer_idx]

                # ✅ 방금 저장된 답변은 바로 완료 메시지로 대체
                if st.session_state.just_saved == answer_idx:
                    fs["done"] = True
                    st.session_state.just_saved = None

                # === 사용자 질문 추출 ===
                # assistant 메시지 직전 user 메시지를 찾아 연결
                question = ""
                if i > 0 and st.session_state.messages[i-1]["role"] == "user":
                    question = st.session_state.messages[i-1]["content"]

                if not fs["done"]:
                    st.markdown("---")
                    st.markdown("**이 답변은 얼마나 만족스러웠나요?**")
                    cols = st.columns(5)
                    for s, col in enumerate(cols, start=1):
                        if col.button(f"⭐ {s}", key=f"star_{answer_idx}_{s}"):
                            fs["rating"] = s

                    if fs["rating"]:
                        st.markdown(f"선택한 별점: {fs['rating']} ⭐")
                        fs["feedback"] = st.text_area("피드백을 남겨주세요.",
                                                      key=f"fb_{answer_idx}",
                                                      value=fs["feedback"])
                        if st.button("피드백 저장", key=f"save_{answer_idx}"):
                            append_feedback(fs["rating"], fs["feedback"], question, msg["content"])
                            fs["done"] = True
                            st.session_state.feedback_states[answer_idx] = fs
                            st.session_state.just_saved = answer_idx  # 다음 렌더링에서 즉시 완료 표시
                            st.rerun()

                else:
                    st.caption("✅ 이 답변은 이미 피드백 완료되었습니다.")

    # === 입력 영역 ===
    prompt = st.chat_input("질문을 입력하세요")
    if prompt:
        with st.chat_message("user"):
            st.write(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.session_state.memory.put(ChatMessage(role="user", content=prompt))

        with st.chat_message("assistant"):
            start = time.time()
            with st.spinner("응답 생성 중..."):
                try:
                    history = st.session_state.memory.get_all()
                    response = stream_chat(model, history)
                    st.write(response)
                    st.caption(f"⏱ {time.time() - start:.2f}초")
                    st.session_state.messages.append({"role": "assistant", "content": response})
                    st.session_state.memory.put(ChatMessage(role="assistant", content=response))
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

if __name__ == "__main__":
    main()
