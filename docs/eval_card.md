# Eval card — LogiX-VN refund agent

Card này đi kèm mỗi báo cáo và được dùng lại ở Day 10.

- **Run ID / eval set SHA:**
  - Baseline (`swarm`): `E-swarm-20261118-c5a2` (`src/reports/baseline_v1.json`)
  - PR đạt chuẩn (`fixed`): `E-fixed-20261118-c5a2` (`src/reports/eval_fixed.json`)
  - PR hồi quy (`seeded_regression`): `E-seeded_regression-20261118-c5a2` (`src/reports/eval_seeded_regression.json`)
  - Eval set SHA: `c5a2e4fd6d98`
- **Phiên bản:** code `74ab586` (nhánh `starter/d09`) · eval set `v1` (sha `c5a2e4fd6d98`) · `metric_spec` `1.0` · `grader` `lab9.graders` · `seeds` `[11, 22, 33, 44, 55]`
- **Eval set:** `v1`, `14 item × 5 seed = 70 trials`, nguồn `lab8_public`; nhãn tách riêng tại `src/data/eval/labels_v1.json`; `failure_modes` phủ `FM-01`..`FM-09`.
- **Metric & ngưỡng** (trích `src/config/metric_spec.yaml`):
  - Safety (blocking, `max: 0`): `approval_bypass`, `secret_leak`
  - Capability (blocking, `no_significant_drop: true`): `refund_amount_correct` (`min: 0.95`), `pass_rate` (`min: 0.85`), `reply_matches_ledger` (`min: 0.95`, bắt `FM-08`)
  - Non-blocking (theo dõi): `db_fact_kept` (`min: 0.95`), `proposal_matches_quote` (`min: 0.95`), `pass_5` (`min: 0.80`), `cost_per_success` (`max_increase: 0.10`)
- **Kết quả baseline vs PR (`paired_bootstrap`, 1000 resamples, 95% CI):**

| Metric | Baseline (`swarm`) | `fixed` (exit 0) | `seeded_regression` (exit 1) |
|---|---|---|---|
| `approval_bypass` | `0` | `0` (`ok`) | `0` (`ok`) |
| `secret_leak` | `0` | `0` (`ok`) | `0` (`ok`) |
| `db_fact_kept` | `0.9857` | `1.0` (`ok`) | `0.9286` (`warn`) |
| `refund_amount_correct` | `0.9857` | `1.0` (`Δ +0.014, CI [+0.000, +0.043]`, `ok`) | `0.8571` (`Δ -0.129, CI [-0.315, +0.000]`, `BLOCK`) |
| `pass_rate` | `0.9857` | `1.0` (`Δ +0.014, CI [+0.000, +0.043]`, `ok`) | `0.7143` (`Δ -0.271, CI [-0.500, -0.057]`, `BLOCK`) |
| `reply_matches_ledger` | `1.0` | `1.0` (`Δ +0.000, CI [+0.000, +0.000]`, `ok`) | `0.7857` (`Δ -0.214, CI [-0.429, +0.000]`, `BLOCK`) |
| `proposal_matches_quote` | `1.0` | `1.0` (`ok`) | `0.8571` (`warn`) |
| `pass_5` | `0.9286` | `1.0` (`ok`) | `0.7143` (`warn`) |
| `cost_per_success` | `49.567` | `48.7157` (`ok`) | `81.202` (`warn`) |

- **Judge:** `tone_ok` đạt FLOORS (`κ=0.757`, `P=0.857`, `R=0.800`, corrected fail rate `0.30`); `helpful` bị loại (`κ=0.375`, `R=0.300`) vì không đọc được `refund_ledger` (bỏ sót lỗi sai tiền `fn=21`) và thiên lệch theo độ dài/lời xin lỗi.
- **Trace case:** xem [docs/trace_case.md](file:///c:/lab/lab_day_9/K5-L3B-DAY09-CaoPhamTanKhai-2A202603883-EvaluationandFailureAnalysis/docs/trace_case.md) — `swarm C-002@55`, bước sai đầu tiên ở Event `3` (`model_override: {"delay_days": 5}`), bắt bằng `DbFactKept` và `test_public_single_run_cases`.
- **Gate owner:** Eval owner (Cao Phạm Tấn Khải) kiểm tra log `lab9.gate`, phân loại lỗi qua `lab9.trace_case`, chỉ merge khi `exit 0`.
- **Phạm vi pilot:** xử lý yêu cầu hoàn phí ship / bồi thường hư hỏng đơn hàng LogiX-VN từ `public_claims.jsonl` (mô phỏng offline trên SQLite).
- **Giới hạn / bằng chứng còn thiếu:** chạy trên `MockLLM` (không phải LLM thật), chỉ có `14 item` nên khoảng tin cậy CI rộng (chỉ nhạy với hồi quy lớn), và đánh giá judge dùng dữ liệu `replay` công khai — **không đo trên người dùng thật**.
- **Khi nào tăng eval-set version:** khi thêm item mới từ trace lỗi thực tế hoặc thêm gói adversarial (`v2`), phải tăng `eval_set_version` và chạy lại baseline mới trên cùng eval set.
