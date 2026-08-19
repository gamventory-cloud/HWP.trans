# -*- coding: utf-8 -*-
"""한글 설문지 -> 워드 설문지 변환기 (Streamlit)
 
    streamlit run app.py
"""
 
import os
import tempfile
 
import streamlit as st
 
from hwp_survey import items_to_dsl, parse_dsl, read_survey, summarize
from hwp_survey.writer import SurveyWriter

st.set_page_config(page_title="설문지 변환기 · 한글 → 워드",
                   page_icon="📋", layout="wide")

st.markdown("""
<style>
  .stTextArea textarea { font-family: 'D2Coding', 'Consolas', monospace;
                         font-size: 13px; line-height: 1.6; }
  div[data-testid="stMetricValue"] { font-size: 1.4rem; }
</style>
""", unsafe_allow_html=True)

DSL_HELP = """
| 표기 | 뜻 |
|---|---|
| `# 제목` | 설문 제목 |
| `> 안내문` | 인사말·연구 목적 |
| `~ 상자글` | 테두리 상자(용어 정의, 유의사항) |
| `## Ⅰ. 섹션` | 섹션 제목 |
| `! 지시문` | 문항 아래 작은 안내 |
| `1. 문항 [단일]` | 문항 + 유형 |
| `- 보기` | 보기 (표 유형이면 표의 행) |
| `-- 소제목` | 표 안 소제목 행 |

**유형 태그** — `[단일]` `[복수]` `[단답]` `[장문]` `[척도:1-7]`
`[표:① 전혀 그렇지 않다,②,③,④,⑤ 매우 그렇다]`
"""


@st.cache_data(show_spinner=False)
def extract(file_bytes: bytes, suffix: str, tighten: bool):
    """업로드된 파일에서 문단·표를 뽑아 중간 텍스트로 만든다."""
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(file_bytes)
        path = tmp.name
    try:
        items = read_survey(path, tighten=tighten)
    finally:
        os.unlink(path)
    stats = {"문단": sum(1 for k, _ in items if k == "p"),
             "표": sum(1 for k, _ in items if k == "table")}
    return items_to_dsl(items), stats


st.title("설문지 변환기")
st.caption("한글(.hwp/.hwpx) 설문지를 워드(.docx) 설문지로 옮깁니다. "
           "표로 만든 리커트 척도 문항까지 표 그대로 살립니다.")

with st.sidebar:
    st.subheader("문서 서식")
    font = st.selectbox("한글 글꼴", ["맑은 고딕", "함초롬돋움", "바탕", "굴림",
                                  "나눔고딕", "HY헤드라인M"], index=0)
    base_pt = st.slider("본문 글자 크기(pt)", 9.0, 12.0, 10.5, 0.5)
    single_mark = st.selectbox("단일 응답 기호", ["○", "□", "◯", "( )"], index=0)
    multi_mark = st.selectbox("복수 응답 기호", ["□", "☐", "[ ]"], index=0)
    row_label_cm = st.slider("표 첫 열 너비(cm)", 5.0, 12.0, 9.0, 0.5)
    accent = st.color_picker("섹션 제목 색", "#1F3B63")

    st.divider()
    st.subheader("추출 옵션")
    tighten = st.toggle("줄바꿈 채움 공백 정리", value=True,
                        help="한글에서 줄 끝을 공백으로 채운 흔적을 붙입니다. "
                             "'만족 감을'→'만족감을'로 살아나지만, 단어 사이를 "
                             "여러 칸 띄운 곳은 붙어버릴 수 있습니다.")

uploaded = st.file_uploader("한글 설문지 올리기", type=["hwp", "hwpx"])

if uploaded is None:
    st.info("변환할 .hwp 또는 .hwpx 파일을 올려주세요. "
            "암호가 걸린 파일과 HWP 3.x 이하 옛 형식은 한글에서 다시 저장한 뒤 올려주세요.")
    with st.expander("중간 텍스트 문법 보기"):
        st.markdown(DSL_HELP)
    st.stop()

suffix = os.path.splitext(uploaded.name)[1].lower()
key = f"{uploaded.name}:{uploaded.size}:{tighten}"

try:
    with st.spinner("한글 파일에서 문단과 표를 읽는 중"):
        dsl, stats = extract(uploaded.getvalue(), suffix, tighten)
except Exception as err:                                  # noqa: BLE001
    st.error(f"파일을 읽지 못했습니다: {err}")
    st.caption("한글에서 '다른 이름으로 저장 → HWPX'로 저장한 파일이 가장 잘 읽힙니다.")
    st.stop()

if st.session_state.get("key") != key:                    # 새 파일이면 편집본 초기화
    st.session_state["key"] = key
    st.session_state["dsl"] = dsl

c1, c2 = st.columns([3, 2], gap="large")

with c1:
    st.subheader("중간 텍스트")
    st.caption("자동 인식이 어긋난 곳을 여기서 고치면 그대로 문서에 반영됩니다.")
    st.session_state["dsl"] = st.text_area(
        "중간 텍스트", value=st.session_state["dsl"], height=520,
        label_visibility="collapsed")
    if st.button("자동 인식 결과로 되돌리기"):
        st.session_state["dsl"] = dsl
        st.rerun()

with c2:
    st.subheader("인식 결과")
    blocks = parse_dsl(st.session_state["dsl"])
    found = summarize(blocks)
    m1, m2 = st.columns(2)
    m1.metric("문단", stats["문단"])
    m2.metric("표", stats["표"])
    m3, m4 = st.columns(2)
    m3.metric("문항", found["문항"])
    m4.metric("섹션", found["섹션"])
    m5, m6 = st.columns(2)
    m5.metric("매트릭스 표", found["매트릭스 표"])
    m6.metric("매트릭스 세부항목", found["매트릭스 세부항목"])

    if found["문항"] == 0:
        st.warning("문항을 하나도 찾지 못했습니다. 왼쪽 텍스트에서 문항 줄을 "
                   "`1. 문항 [단일]` 형태로 맞춰주세요.")

    writer = SurveyWriter(font=font, base_pt=base_pt, single_mark=single_mark,
                          multi_mark=multi_mark, row_label_cm=row_label_cm,
                          accent=accent.lstrip("#").upper())
    docx_bytes = writer.write(blocks).to_bytes()
    out_name = os.path.splitext(uploaded.name)[0] + ".docx"

    st.download_button("워드 파일 내려받기", data=docx_bytes, file_name=out_name,
                       mime="application/vnd.openxmlformats-officedocument."
                            "wordprocessingml.document",
                       type="primary", use_container_width=True)
    st.download_button("중간 텍스트 내려받기", data=st.session_state["dsl"],
                       file_name=os.path.splitext(uploaded.name)[0] + ".txt",
                       mime="text/plain", use_container_width=True)

    with st.expander("문법 도움말"):
        st.markdown(DSL_HELP)
