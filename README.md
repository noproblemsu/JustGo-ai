
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

**JustGo**는 사용자가 입력한 여행지, 날짜, 예산, 여행 스타일, 동반자 정보를 바탕으로 GPT와 네이버 API를 활용해 맞춤형 관광지·맛집 추천부터 대화형 일정 조율까지 지원하는 오픈소스 여행 일정 추천 플랫폼입니다.
추천된 장소는 네이버 지도 리뷰 연동을 통해 실시간 검증이 가능하며, 사용자는 챗봇과 대화를 통해 일정을 자유롭게 수정할 수 있습니다.
또한 모바일 친화적인 UI와 직관적인 인터페이스로, 지도에서 동선을 확인·조정하고 PDF로 여행 계획을 내보낼 수 있습니다.

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
/*
 * =====================================================================
 * 프로젝트에 사용된 오픈소스 라이브러리 목록
 *
 * 본 파일은 프로젝트의 기술 스택을 요약하여 README에 포함하기 위한
 * C언어 형식의 가이드입니다.
 * =====================================================================
 */

#include <stdio.h>

// 프로젝트의 주요 오픈소스 라이브러리들을 정의합니다.
// 각 라이브러리의 역할과 프로젝트 내 사용처를 명시합니다.
typedef struct {
    const char* name;          // 라이브러리 이름
    const char* description;   // 라이브러리 설명
    const char* usage;         // 프로젝트 내 주요 사용처
} ProjectLibrary;

enum LibraryCount {
    NUM_LIBRARIES = 6
};

// 프로젝트 기술 스택
const ProjectLibrary libraries[NUM_LIBRARIES] = {
    {
        .name        = "Streamlit",
        .description = "Python으로 데이터 웹 앱을 쉽게 만드는 프레임워크",
        .usage       = "사용자 입력(여행지, 기간, 예산)을 받는 UI 구축 및 AI 추천 결과 표시"
    },
    {
        .name        = "OpenAI",
        .description = "GPT 모델 API 호출을 위한 공식 Python 라이브러리",
        .usage       = "사용자 조건에 맞는 여행 일정 및 장소(관광지, 맛집) 추천"
    },
    {
        .name        = "requests",
        .description = "HTTP 요청을 간편하게 처리하는 Python 라이브러리",
        .usage       = "네이버 검색 API, Google Places API 등 외부 서비스와 통신"
    },
    {
        .name        = "python-dotenv",
        .description = ".env 파일의 환경 변수를 로드하는 라이브러리",
        .usage       = "API 키(OPENAI_API_KEY 등)와 같은 민감한 정보를 안전하게 관리"
    },
    {
        .name        = "FastAPI",
        .description = "고성능 웹 API 서버 구축에 최적화된 프레임워크",
        .usage       = "여행 일정 수정 등 백엔드 로직을 처리하는 API 엔드포인트 정의"
    },
    {
        .name        = "Pydantic",
        .description = "데이터 유효성 검증 및 설정 관리를 위한 라이브러리",
        .usage       = "API 요청(Request) 및 응답(Response) 데이터의 형식 정의 및 검증"
    }
};


// C 코드 예시 (README 생성 기능)
void generate_readme_section() {
    printf("## 🛠️ 프로젝트에 사용된 기술 스택\n\n");
    for (int i = 0; i < NUM_LIBRARIES; i++) {
        printf("### %s\n", libraries[i].name);
        printf("- **설명**: %s\n", libraries[i].description);
        printf("- **주요 사용처**: %s\n\n", libraries[i].usage);
    }
}
---

## 📂 폴더 구조


## 🗺 JustGo 서비스 흐름
![JustGo 서비스 흐름](docs/images/justgo_service_flow_dark_v13_readme.png)

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



---

## 2. 주요 기능
여행 정보 입력 & 추천
입력한 여행지, 날짜, 예산, 동반자, 여행 스타일을 반영해 맞춤형 관광지·맛집 추천

일정 생성 (챗봇)
추천된 장소를 기반으로 맞춤형 일정 생성, 타임테이블·지도·동선 자동 구성

대화형 일정 조율 (GPT)
마음에 드는 일정을 선택 후 챗봇과 대화를 통해 실시간 수정(장소 추가·삭제·순서 변경)

네이버 지도 리뷰 연동
관광지·맛집 클릭 시 네이버 지도 리뷰로 바로 이동해 실시간 검증 가능

PDF 일정 내보내기
생성된 일정을 PDF 파일로 저장 가능

모바일 친화 UI
카드형·메신저형 인터페이스로 직관적인 사용 경험 제공
---

## 🗺 서비스 흐름
![JustGo 서비스 흐름](docs/images/justgo_service_flow_dark_v13_readme.png)

---

## 3. UI 스크린샷
| 메인 페이지 | 챗봇 일정 생성 | 지도 보기 |
|-------------|--------------|-----------|
| ![메인](docs/images/main.png) | ![챗봇](docs/images/chat.png) | ![지도](docs/images/map.png) |

---



---

## 5. 설치 및 실행 방법
```bash
# 1. 저장소 클론
git clone https://github.com/사용자명/JustGo.git
cd JustGo

# 2. 가상환경 생성 및 활성화
python -m venv venv
venv\Scripts\activate   # (Windows)
source venv/bin/activate  # (Mac/Linux)

# 3. 의존성 설치
pip install -r requirements.txt

# 4. 서버 실행
uvicorn backend.main:app --reload

