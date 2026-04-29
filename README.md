# llm-evalbox

> OpenAI 호환 (`/v1/chat/completions`, `/v1/responses`) 엔드포인트의 `BASE_URL` + `MODEL_NAME` 두 가지만으로 학술 벤치마크(MMLU / GSM8K / HumanEval / TruthfulQA / HellaSwag …)를 CLI 또는 로컬 웹 UI 로 즉시 실행하는 경량 평가 도구.

상태: **M0 (Core + 최소 CLI) 개발 중**. 자세한 설계는 [`PLAN.md`](./PLAN.md), 작업 가이드는 [`CLAUDE.md`](./CLAUDE.md).

## 빠른 시작

```bash
pip install -e ".[dev]"
cp .env.example .env   # EVALBOX_BASE_URL, EVALBOX_MODEL, OPENAI_API_KEY 채우기
evalbox doctor         # 연결 + capability 체크
evalbox run --bench mmlu --samples 50
```

## 라이선스

Apache-2.0. 데이터셋은 번들하지 않으며 첫 실행 시 manifest 기반으로 다운로드한다 (sha256 검증).
