# 🌍 JustGo — AI 기반 맞춤 여행 일정 추천 플랫폼
[![GitHub stars](https://img.shields.io/github/stars/사용자명/저장소명?style=social)](https://github.com/사용자명/저장소명/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/사용자명/저장소명?style=social)](https://github.com/사용자명/저장소명/network/members)
[![GitHub issues](https://img.shields.io/github/issues/사용자명/저장소명)](https://github.com/사용자명/저장소명/issues)
[![GitHub last commit](https://img.shields.io/github/last-commit/사용자명/저장소명)](https://github.com/사용자명/저장소명/commits/main)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](/LICENSE)
![Made with Python](https://img.shields.io/badge/Made%20with-Python-blue)
![Frontend](https://img.shields.io/badge/Frontend-HTML%20%7C%20CSS%20%7C%20JS-yellow)
![OpenAI API](https://img.shields.io/badge/API-OpenAI%20GPT-blue)
![Naver API](https://img.shields.io/badge/API-Naver%20Place%20Review-green)

> **입력 → 추천 → 선택 → 일정 생성 → 챗봇 수정**
>
> 사용자가 입력한 **여행지, 날짜, 예산, 동반자, 스타일**을 바탕으로 관광지/맛집을 추천하고, 사용자가 고른 **가고 싶은 장소**와 입력된 여행지, 날짜, 예산, 동반자, 스타일 정보를 반영해 일정을 생성합니다. 이후 **챗봇과의 대화로 실시간 수정**까지 이어지는 완전한 여정을 제공합니다.

---

## ✨ 데모

* 🎬 **시연 영상**: (추가 예정)

---

## 🎯 배경 & 목표

* 폼 입력만으로 끝나는 여행앱을 넘어, **대화형**으로 계획을 세우고 증거 기반(리뷰/지도)으로 선택하게 합니다.
* **GPT**와 **네이버 장소/리뷰 API**를 결합하여 추천의 품질과 신뢰도를 동시에 확보합니다.
* 일정은 생성으로 끝나지 않습니다. **챗봇과의 대화**로 즉시 수정·재구성이 가능합니다.

## 🗺 서비스 흐름
![화면 예시](docs/images/제목을-입력해주세요_-001.png)

1. **여행 정보 입력**  → 날짜 선택, 스타일 지정 (Flatpickr, Swiper 등 사용)

2. **추천 생성**  → GPT가 후보 장소 제안, 네이버 API로 리뷰·지도 링크 보강

3. **사용자 선택**  → 가고 싶은 관광지·맛집 선택

4. **일정 생성**  → GPT가 예산과 선호 반영 일정 생성

5. **챗봇 수정**  → 자연어로 일정 변경 요청 및 즉시 반영

6. **일정 저장**  → 일정 홈화면에 저장 및 PDF 다운로드
---

## 🧵 사용자 여정 & 오픈소스 사용 흐름

아래는 JustGo의 전체 흐름과 각 단계에서 활용되는 **오픈소스/외부 API**입니다.


### 1) 홈화면 — 저장된 일정 한눈에
<p align="center">
  <img src="docs/images/1.png" width="20%" alt="화면 예시">
</p>

* **사용자 행동**

   * 최근에 일정확인으로 저장한 일정들이 카드 형태로 표시됨
   * 카드를 탭/클릭해 상세 보기로 이동
   * 새 여행 시작 버튼으로 입력 단계로 진입
   * 상단 오른쪽 집 아이콘을 누르면 언제든 이 홈화면으로 돌아옴



* **데이터 흐름 & 규칙**

   * 진입 시 GET /api/itinerary/list 호출 → 저장된 일정 목록을 렌더링
   * 최근 확정된 일정은 최상단에 노출
   * 카드 탭 시 해당 일정 id로 상세(또는 챗봇 수정 화면) 라우팅
   * 로컬 임시값(localStorage)은 목록 표시용이 아니라 **서버 목록이 단일 진실원천(SSOT)**

* **백엔드 로직**

   * GET /api/itinerary/list : 사용자별 저장 일정 목록 반환 (id, title, dates, totalCost, updatedAt 등)
   * 페이지네이션/정렬(최근 업데이트순) 지원


> 사용 오픈소스: **FastAPI**, **Pydantic**, **httpx**, **Istok Web**, **fetch**, **localStorage** 

### 2) 입력 단계 — 여행지·날짜·예산·동반자·스타일 수집
<p align="center">
  <img src="docs/images/2.png" width="70%" alt="화면 예시">
</p>
* **사용자 행동**
  *  `여행지, 날짜(기간), 예산, 동반자(친구/가족/반려동물 등), 스타일(힐링/액티비티/미식 등)`을 모바일 친화 UI에서 입력합니다.
* **프론트엔드 구성 요소**

  * 날짜 선택: **Flatpickr (MIT)**
  * 폰트: **Istok Web (OFL 1.1)**
  * 네트워킹: **fetch (브라우저 내장)**
  * 카드 슬라이드 UI: **Swiper (MIT)**
* **데이터 흐름 & 규칙**

  * 입력값은 `localStorage`에 임시 저장 후 **FastAPI** 백엔드로 전송
  * `확인` → 입력값 저장 후 다음 페이지 이동 / `다음에 하기` → 저장 없이 이동
  * 날짜: 과거 선택 불가
  * 예산: 입력 시 자동 **3자리 콤마** 표기(저장은 숫자만)

> 사용 오픈소스: **Flatpickr(MIT)**, **Istok Web(OFL)**, **Swiper (MIT)**

---

### 2) 1차 추천 — 관광지·맛집 리스트 제안
<p align="center">
  <img src="docs/images/3.png" width="70%" alt="화면 예시">
</p>

* **프론트엔드 구성요소**
   *  정렬/필터 토글, 태그 바(상단에 현재 입력값 노출)
* **데이터 흐름 & 규칙**
   *  프론트엔드가 서버에 추천 요청 → 서버가 GPT로 초기 후보 생성 → 네이버 장소/리뷰 API로 평판·지도 링크 보강 후 반환
* **백엔드 로직**
   *  입력값을 바탕으로 GPT에 "이 도시/예산/스타일" 조건을 전달해 후보기관광지/맛집을 생성하고, 각 후보에 대해 **네이버 장소/리뷰 API**로 실제 평판·리뷰·지도 검색 링크를 보강합니다.

* **응답 예시**

```jsonc
{
  "attractions": [
    { "name": "성산일출봉", "rating": 4.6, "mapUrl": "https://map.naver.com/...", "reviews": ["경치가 최고", "일출이 아름다움"] },
    { "name": "만장굴", "rating": 4.4, "mapUrl": "https://map.naver.com/...", "reviews": ["시원", "신비로운 동굴"] }
  ],
  "restaurants": [
    { "name": "제주흑돈집", "rating": 4.5, "mapUrl": "https://map.naver.com/...", "reviews": ["고기 질이 좋음"] }
  ]
}
```

> 사용 오픈소스: **FastAPI, Pydantic, Starlette, Uvicorn, httpx, python-dotenv, tenacity, OpenAI SDK**

---

### 4) 선택 — 내가 가고 싶은 곳 고르기

* **사용자 행동**
  *  추천된 관광지/맛집 중 **가고 싶은 후보**에 체크/선택합니다.
* **프론트엔드 UI**
  * 카드/토글 선택 → 선택 결과를 요약해 보여주고, 다음 단계로 진행 버튼 제공.
* **데이터 흐름 & 규칙**
  *  `선택 관광지[]`, `선택 맛집[]`을 기존 입력값과 함께 백엔드로 전송합니다. 확인은 저장 후 이동, 다음에 하기는 저장 없이 이동.
* **백엔드 로직**
  *  선택 항목 유효성(중복/최대개수/지도 좌표 유무) 검사 → 세션 컨텍스트에 병합 저장
> 사용 오픈소스: **Flatpickr(MIT)**, **Istok Web(OFL)**

---

### 5) 여행 정보 세팅 페이지 — 전체 값 검토/수정
<p align="center">
  <img src="docs/images/4.png" width="20%" alt="화면 예시">
</p>

* **사용자 행동**

  * 지금까지 입력·선택한 정보를 한 화면에서 확인
  * 각 항목(파란 라벨) 클릭 → 해당 입력 페이지로 이동해 수정 → 저장 시 세팅 페이지로 복귀

* **프론트엔드 구성요소**

  * 요약 카드 리스트, 라벨 클릭 네비게이션, "일정 생성하기" CTA

* **데이터 흐름 & 규칙**

  * 프론트가 서버에서 세션 컨텍스트 조회 → 표시
  * 수정 저장 시 세팅 페이지로 **항상 복귀**

* **백엔드 로직**

  * 세션 컨텍스트 집계 API(`GET /api/context`) 제공, 부분 수정 `PATCH` 지원

**응답 예시(`GET /api/context`)**

```json
{
  "destination": "제주도",
  "dates": ["2025-08-15", "2025-08-18"],
  "budget": 500000,
  "companions": ["친구"],
  "styles": ["액티비티"],
  "intensity": 3,
  "selectedAttractions": ["성산일출봉", "만장굴"],
  "selectedRestaurants": ["제주흑돈집"]
}
```

> 사용 오픈소스: **FastAPI**, **Pydantic**, (선택) **Redis/DB**

---

### 6) 일정 생성 — 입력값 + 선택 장소 기반 맞춤 일정
<p align="center">
  <img src="docs/images/6.png" width="20%" alt="화면 예시">
</p>

* **백엔드 로직**
  * `여행지, 날짜, 예산, 동반자, 스타일, 선택 관광지[], 선택 맛집[]`을 종합해 현실적인 동선/소요시간/식사타임을 고려한 일정을 GPT로 생성합니다.
* **예상 비용**
  * 하루 단위 비용을 합산하여 **일정 총액**을 계산(예산 준수). 응답에는 **총액만** 명시하도록 통제합니다.
* **데이터 흐름 & 규칙**
  * 서버에 생성 요청 → GPT가 예산 ±15% 준수, 동선/식사/소요시간 고려 일정 생성
  * 총액은 일정 단위로만 표기(아이템 단가 노출 안 함)
* **응답 예시**

```jsonc
{
  "itinerary": {
    "title": "제주 힐링 코스",
    "days": [
      {
        "date": "2025-08-15",
        "plan": [
          { "time": "오전", "place": "성산일출봉", "note": "일출 감상 후 카페" },
          { "time": "점심", "place": "제주흑돈집", "note": "근처 이동" },
          { "time": "오후", "place": "만장굴", "note": "동굴 탐방" }
        ]
      }
    ],
    "totalCost": 480000
  }
}
```

* **오픈소스/외부 API**: 2단계와 동일 스택 + **OpenAI GPT** 프롬프트 제어(비용 규칙·형식 규약·누락 방지).

> 사용 오픈소스: **OpenAI SDK, FastAPI, Pydantic, httpx**

---

### 7) 챗봇 수정 — 자연어로 즉시 재구성
<p align="center">
  <img src="docs/images/6.png" width="20%" alt="화면 예시">
</p>

* **사용자 행동**
  *  생성된 일정을 보며 챗봇에 자연어로 수정 요청

  *  예) "둘째 날 저녁을 바다 전망 식당으로 바꿔줘",
  *  예) "비 오면 실내 활동으로 플랜 B 추가"
* **데이터 흐름 & 규칙**
  * 현재 itinerary state와 사용자 메시지를 함께 서버로 전송
  * 서버는 GPT로부터 변경 diff를 받아 서버 측에서 병합 → 검증 후 변경된 일정 반환

UI는 변경된 구간만 부분 리렌더링
* **백엔드 로직**
  * 현 상태(itinerary state)를 시스템 메시지로 제공
  * 사용자의 수정 의도를 파싱해 **변경 diff**를 GPT로부터 받아 **서버에서 병합**
  * 스키마(Pydantic)로 검증 → 예산 초과/시간 충돌 검사 → 충돌 시 대안 제시.
* **UI 반영**
  * 수정된 구간만 빠르게 리렌더링(카드 확장/토글 유지).
* **일정 추천 기본 구조**
  * GPT가 생성하는 모든 일정은 아침·점심·저녁 3끼가 고정으로 포함
  * 각 식사 사이사이에 관광지 일정을 자동 배치
  * 이후 챗봇 대화를 통해 일정 강도(여유롭게/빡세게)나 활동 시간대(오전/오후) 등을 자유롭게 수정 가능

> 사용 오픈소스: **OpenAI SDK, FastAPI, Pydantic, httpx, tenacity**

---

### 8) 일정 확정 & 저장 — 홈화면/파일 출력
<p align="center">
  <img src="docs/images/8.png" width="40%" alt="화면 예시">
</p>

* **사용자 행동**

  *  일정 카드에서 **“일정확인” 버튼**을 누르면 해당 일정이 확정됩니다.
  *  확정된 일정은 홈화면의 **저장된 일정 목록**에 바로 표시됩니다.
  *  **PDF로 저장** 버튼을 눌러 여행 일정을 파일로 내려받을 수 있습니다.
  *  

     
* **데이터 흐름 & 규칙**

  *  일정확인 시 현재 선택된 `itinerary`를 \*\*서버(영구 저장소)\*\*와 \*\*localStorage(로컬 임시)\*\*에 저장합니다.
  *  홈화면 진입 시 서버 저장 목록을 조회하여 **UI에 렌더링**합니다.
  *  PDF 저장 요청 시 프론트 → 서버로 요청, 서버가 최신 일정으로 **PDF 생성** 후 다운로드 링크 반환.
  *  규칙: 이미 저장된 일정은 **중복 저장 방지**, PDF는 **가장 최근 상태**만 반영.

* **백엔드 로직**

  *  `POST /api/itinerary/confirm` : 선택된 일정을 식별자와 함께 저장(DB/스토리지)
  *  `GET  /api/itinerary/list`    : 저장된 일정 목록 조회(홈화면 표시용)
  *  `POST /api/itinerary/pdf`     : 일정 데이터를 받아 **PDF 생성** 후 파일/URL 반환
  *  PDF에는 **여행지·날짜·일별(아침/점심/저녁 + 활동)·총예산**을 표 또는 카드 레이아웃으로 출력

* **UI 반영**

  *  홈화면에 **“내 일정”** 섹션을 두고, 방금 확정한 일정을 최상단에 표시합니다.
  *  일정확인 시 **Toast/Alert**로 “일정이 저장되었습니다” 안내 후 홈으로 라우팅합니다.
  *  PDF 버튼 클릭 시 브라우저 **다운로드 다이얼로그**가 열리며 저장됩니다.

> 사용 오픈소스: **FastAPI**, **Pydantic**, **ReportLab**, **WeasyPrint**, **localStorage**


---

### 9) 공통 — 오류/보안/성능

* **오류 처리**

  * 외부 API 실패 시 **tenacity**로 백오프 재시도, 타임아웃/대체안 안내

* **보안/프라이버시**

  * API 키는 서버 `.env`(클라이언트 미노출), 입력값 최소 수집/필요 시점에만 저장

* **성능/캐시**

  * 추천 응답은 목적지·필터 기준 캐시, 컨텍스트는 세션 캐시(예: Redis)

---




## 🏗 시스템 아키텍처

```
[Frontend] HTML/CSS/JS
   └─(fetch)→ [Backend] FastAPI
        ├─ OpenAI(GPT) : 일정 생성/수정, 추천 보강
        └─ Naver API   : 장소 검색/리뷰/지도 링크
```

* **Frontend**: HTML/CSS/JS, localStorage, Flatpickr
* **Backend**: FastAPI, Pydantic, httpx, OpenAI SDK
* **Infra(예시)**: uvicorn, dotenv, 로깅(loguru 등 선택)

---

## 📱 주요 화면 (이미지는 추후 추가)

1. **여행 설정** — 입력 폼(여행지/날짜/예산/동반자/스타일)
2. **추천 결과** — 관광지·맛집 카드 + 리뷰/지도 링크
3. **선택 요약** — 내가 고른 후보 확인 → 일정 생성 버튼
4. **일정 보기** — 카드형 요약, 클릭 시 상세 토글
5. **챗봇 수정** — 자연어로 일정 수정/재추천
6. **지도 보기** — 선택 일정 동선/장소 표시

---

## 🧰 기술 스택

* **Frontend**: HTML, CSS, JavaScript, **Flatpickr(MIT)**, **Istok Web(OFL)**
* **Backend**: **FastAPI(MIT)**, **Pydantic(MIT)**, **Starlette(BSD-3)**, **Uvicorn(BSD-3)**, **httpx(BSD-3)**, **python-dotenv(BSD-2)**, **tenacity(Apache-2.0)**
* **AI**: **OpenAI Python SDK v1 (MIT)**
* **External**: **Naver Search/Place Review API**

---

## 🚀 빠른 시작

```bash
# 1) Backend
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
cp .env.example .env  # OPENAI, NAVER 키 입력
uvicorn main:app --reload --port 8000

# 2) Frontend
# 정적 파일을 브라우저로 직접 열거나(개발용), 간단 서버 사용
# Python
python -m http.server 5173 -d frontend
# 또는 Node
npx serve frontend -l 5173
```

---

## 🔧 환경 변수(.env)

```ini
OPENAI_API_KEY=
NAVER_CLIENT_ID=
NAVER_CLIENT_SECRET=
```

---

## 📡 API 개요

### 1) 추천 (관광지·맛집)

`POST /api/recommend/places`

```jsonc
{
  "destination": "제주도",
  "dates": ["2025-08-15", "2025-08-18"],
  "budget": 500000,
  "companions": ["친구"],
  "style": "액티비티"
}
```

**응답**: attractions\[], restaurants\[] (각 name, rating, mapUrl, reviews\[])

### 2) 일정 생성

`POST /api/plan`

```jsonc
{
  "destination": "제주도",
  "dates": ["2025-08-15", "2025-08-18"],
  "budget": 500000,
  "companions": ["친구"],
  "style": "액티비티",
  "selectedAttractions": ["성산일출봉", "만장굴"],
  "selectedRestaurants": ["제주흑돈집"]
}
```

**응답**: itinerary{ title, days\[], totalCost }

### 3) 일정 수정(챗봇)

`POST /api/plan/update`

```jsonc
{
  "itinerary": { /* 현 일정 전체 */ },
  "message": "둘째 날 저녁 바다 전망 식당으로 바꿔줘"
}
```

**백엔드 처리**: GPT가 수정 diff 제안 → 서버에서 병합 → 스키마/예산/시간 충돌 검증 → 갱신된 itinerary 반환

---

## 🗃 데이터 모델(요약)

```ts
// Request: RecommendPlaces
{
  destination: string;
  dates: [string, string];
  budget: number;
  companions: string[];
  style: string;
}

// Response: RecommendPlaces
{
  attractions: Place[];
  restaurants: Place[];
}

// Request: Plan
{
  destination: string;
  dates: [string, string];
  budget: number;
  companions: string[];
  style: string;
  selectedAttractions: string[];
  selectedRestaurants: string[];
}

// Itinerary
{
  title: string;
  days: { date: string; plan: { time: string; place: string; note?: string }[] }[];
  totalCost: number; // 예산 ±15% 내
}
```

---

## 🔐 보안 & 프라이버시

* **키 관리**: `.env`(OPENAI/NAVER) — 서버만 보유, 프론트 미노출
* **최소 수집**: 필요한 정보 외 저장 없음, 임시 선택값은 `localStorage` 사용
* **입출력 검증**: Pydantic 스키마, 타입·범위 검증
* **예산·시간 검증**: 총액(±15%), 동선/시간 충돌 검사
* **오류/재시도**: 외부 API 장애 시 **tenacity**로 백오프 재시도

---

## 🗺 로드맵

* [ ] 날씨 API 연동(우천 시 자동 대체 코스)
* [ ] 다국어 프롬프트/UI 지원
* [ ] 지도 경로 시각화(마커/클러스터/경로 최적화)
* [ ] 사용자 선호 학습(히스토리 기반 개인화)


---

## 📄 라이선스 & 오픈소스 고지

* 프로젝트 라이선스: **MIT License**
* 사용 오픈소스 및 라이선스(주요)

  * **FastAPI** (MIT)
  * **Pydantic** (MIT)
  * **Starlette** (BSD-3-Clause)
  * **Uvicorn** (BSD-3-Clause)
  * **httpx** (BSD-3-Clause)
  * **OpenAI Python SDK** (MIT)
  * **python-dotenv** (BSD-2-Clause)
  * **tenacity** (Apache-2.0)
  * **Flatpickr** (MIT)
  * **Istok Web Font** (OFL-1.1)






---

