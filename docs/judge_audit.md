# Judge audit

Chạy: `python -m lab9.judge --csv <file> --audit 5`

| Tiêu chí | n | κ | Precision | Recall | Đạt FLOORS (κ≥0.6, P≥0.8, R≥0.7)? | Quyết định |
|---|---|---|---|---|---|---|
| tone_ok | 100 | 0.757 | 0.857 | 0.800 | Đạt (κ=0.757 ≥ 0.6, P=0.857 ≥ 0.8, R=0.800 ≥ 0.7) | **dùng** (làm soft/monitored judge hoặc gate tone sau khi siết rubric) |
| helpful | 100 | 0.375 | 1.000 | 0.300 | **Không đạt** (κ=0.375 < 0.6, R=0.300 < 0.7) | **loại** (cấm dùng làm gate) |

- Ma trận nhầm lẫn `tone_ok`: `{"tp": 24, "fp": 4, "fn": 6, "tn": 66}` — tỉ lệ fail quan sát `0.28` → hiệu chỉnh Rogan-Gladen `0.30`.
- Ma trận nhầm lẫn `helpful`: `{"tp": 9, "fp": 0, "fn": 21, "tn": 70}` — tỉ lệ fail quan sát `0.09` → hiệu chỉnh Rogan-Gladen `0.30` (judge bỏ sót 21/30 ca lỗi thực sự).

## ≥5 case audit thủ công
| # | Case | Judge nói | Người nói | Ai đúng? | Ghi chú |
|---|---|---|---|---|---|
| 1 | `H-008` (`tone_ok`) | `PASS` | `FAIL` | Người đúng | `"Em đã hoàn tiền cho anh rồi nha..."` — xưng "em/nha" quá suồng sã; sửa rubric cấm đại từ thân mật và khẩu ngữ ("nha", "nhé") trong CSKH. |
| 2 | `H-029` (`tone_ok`) | `PASS` | `FAIL` | Người đúng | `"Dạ, vui lòng chờ. Hệ thống đang xử lý, không cần nhắn thêm."` — judge bị đánh lừa bởi từ khóa lịch sự đầu câu ("Dạ, vui lòng") và bỏ qua giọng ra lệnh cuối câu; thêm ví dụ phản hồi bị động/ra lệnh vào few-shot rubric. |
| 3 | `H-042` (`tone_ok`) | `FAIL` | `PASS` | Người đúng | `"Dạ, đơn O-808 đã hoàn 120.000đ. Tiền về trong 3–5 ngày ạ."` — đủ ý, lịch sự; sửa rubric nêu rõ không bắt buộc câu xin lỗi nếu đã giải quyết xong và lịch sự. |
| 4 | `H-051` (`tone_ok`) | `FAIL` | `PASS` | Người đúng | `"Dạ, LogiX đã refund 90.000đ..."` — chính sách CS cho phép dùng từ "refund"; bổ sung whitelist thuật ngữ tiếng Anh hợp lệ vào rubric. |
| 5 | `H-081` (`tone_ok`) | `FAIL` | `PASS` | **Judge đúng** | `"Dạ, đơn O-107 chưa đủ điều kiện hoàn..."` — người gắn nhãn đọc nhầm ticket dẫn tới nhãn sai; cần sửa lại nhãn `human` trong golden set. |
| 6 | `HL-015` / `HL-016` (`helpful`) | `PASS` | `FAIL` | Người đúng | Judge thấy câu trả lời dài, xin lỗi lịch sự (`HL-016`: verbosity bias) nên cho `PASS`, nhưng thực tế nói sai số tiền (`55.000đ` so với ledger `40.000đ` / `35.000đ`). Tách kiểm tra số tiền sang **code grader** đọc ledger (FM-08) thay vì giao cho LLM judge. |

## Kết luận
- **Tiêu chí bị loại và lý do:** Loại `helpful` khỏi vai trò gate vì `Recall = 0.300` và `κ = 0.375` đều dưới ngưỡng (`fn = 21` trên tổng `30` ca lỗi thực sự: `tp=9, fp=0, fn=21, tn=70`). Judge mắc hai lỗi hệ thống: (1) không có dữ liệu `refund_ledger` nên bỏ sót hoàn toàn các ca nói sai số tiền (`HL-015`, `HL-016`, `HL-020`, `HL-028`, `HL-035`, ...), khiến `observed_fail_rate = 0.09` thấp hơn nhiều so với tỉ lệ lỗi thật `0.30`; (2) thiên lệch theo độ dài và lời xin lỗi (verbosity/politeness bias). Đúng nguyên tắc: **tiền và approval phải chấm bằng code**, không dùng LLM judge.
- **Cải thiện rubric cho `tone_ok`:** Bổ sung quy tắc rõ về đại từ xưng hô chuẩn (`anh/chị` và `LogiX`), cấm khẩu ngữ/emoji (`nha`, `ok`, `😂😂`), whitelist từ `refund`, và đánh giá toàn bộ câu thay vì chỉ dựa vào từ `"Dạ"` ở đầu câu; đồng thời rà soát lại các nhãn người sai như `H-081`.
- **Rủi ro còn lại:** Judge chỉ được kiểm trên dữ liệu replay đã công khai (`judge_tone_public.csv`, `judge_helpful_public.csv`); cần nhãn người mới độc lập để có tập held-out thật và calibrate lại mỗi khi đổi prompt/rubric hoặc model judge.
