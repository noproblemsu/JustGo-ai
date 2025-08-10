
# JustGo ✈️

[![GitHub stars](https://img.shields.io/github/stars/사용자명/저장소명?style=social)](https://github.com/사용자명/저장소명/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/사용자명/저장소명?style=social)](https://github.com/사용자명/저장소명/network/members)
[![GitHub issues](https://img.shields.io/github/issues/사용자명/저장소명)](https://github.com/사용자명/저장소명/issues)
[![GitHub last commit](https://img.shields.io/github/last-commit/사용자명/저장소명)](https://github.com/사용자명/저장소명/commits/main)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](/LICENSE)
![Made with Python](https://img.shields.io/badge/Made%20with-Python-blue)
![Frontend](https://img.shields.io/badge/Frontend-HTML%20%7C%20CSS%20%7C%20JS-yellow)
![OpenAI API](https://img.shields.io/badge/API-OpenAI%20GPT-blue)
![Naver API](https://img.shields.io/badge/API-Naver%20Place%20Review-green)

**JustGo**는 사용자가 입력한 여행지, 날짜, 예산, 여행 스타일, 동반자 정보를 바탕으로 인공지능이 3개의 맞춤 여행 일정을 생성하고, 사용자가 직접 선택·수정할 수 있는 오픈소스 여행 일정 추천 플랫폼입니다. 단순 추천이 아니라, **네이버 지도 리뷰 연동**으로 실시간 리뷰를 확인하며 검증 가능한 정보를 제공합니다. 모바일 친화적인 UI와 직관적인 챗봇 인터페이스로, 여행 계획 과정을 쉽고 재미있게 만듭니다.

---

## 🚀 주요 기능
- **일정 3개 자동 생성**  
  GPT가 3개의 서로 다른 스타일(힐링, 자연, 먹기 중심)로 3일치 일정을 한 번에 제안
- **예산 제약 반영**  
  각 일정의 총 예상 비용이 입력 예산의 ±15% 범위를 반드시 준수
- **세부 일정 구성**  
  하루 3개 활동(아침/점심/저녁) 포함, 시간·소요시간·비용 정보 제공
- **챗봇 기반 일정 조율**  
  마음에 드는 일정 선택 후 대화로 수정
- **네이버 지도 연동**  
  관광지·맛집을 클릭하면 네이버 지도 리뷰로 바로 이동
- **모바일 최적화 UI**  
  카드형·메신저형 인터페이스로 직관적 사용 경험 제공

---

## 🛠 기술 스택
- **Frontend**: HTML, CSS, JavaScript (모바일 퍼스트)
- **Backend**: Python, FastAPI (API), Streamlit (개발 UI)
- **AI**: OpenAI GPT API (Python v1.x SDK)
- **외부 데이터**: 네이버 장소·리뷰 API

---

## 📂 폴더 구조

# 1. 저장소 클론
git clone https://github.com/사용자명/저장소명.git
cd 저장소명

# 2. 라이브러리 설치
pip install -r requirements.txt

# 3. 서버 실행
uvicorn main:app --reload

# 4. 브라우저 접속
http://localhost:8000


---

💡 이렇게 하면  
- **Mermaid 다이어그램**으로 서비스 흐름 시각화  
- **사진 & GIF**로 기능이 직관적으로 보임  
- 핵심 기능이 순서대로 정리  

지금 이미지랑 GIF만 준비하면 바로 README에 적용 가능합니다.  

원하면 제가 **UI 캡처 어떻게 찍고 GIF 만드는 방법**까지 알려줄까요?  
그렇게 하면 완성본 바로 만들 수 있습니다.

