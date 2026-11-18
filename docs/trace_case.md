# Trace case: từ trace tới quyết định sai đầu tiên

Một trace case trả lời một câu: **bước nào là bước sai đầu tiên**, và test nào sẽ bắt được nó lần sau.

```bash
cd src
python -m lab9.trace_case --shape seeded_regression --claim C-002 --seed 11
python -m lab9.trace_case --shape fixed --claim C-002 --seed 11   # đối chứng
```

Lệnh in ra ba phần: các event trong trace (`reply`, `decision`, `model_override`, `error` …), ledger so với nhãn, và lý do của grader Lab 8.

## Mẫu điền (mỗi bạn 1 case, lấy từ trial đang fail trong report)

| Trường | Nội dung |
|---|---|
| Trial | `swarm C-002@55` (trace đối chứng trực tiếp từ `python -m lab9.trace_case --shape swarm --claim C-002 --seed 55`) |
| Triệu chứng | `lab8` grader FAIL (`status resolved != denied`); ledger ghi `refund_vnd=20000`, `refund_count=1` trong khi label yêu cầu `status=denied`, `refund_vnd=0`, `refund_count=0`. |
| Bước sai đầu tiên | Event `3`: `model_override` — `{"delay_days": 5}` |
| Vì sao là bước *đầu tiên* | Event `1` (`handoff`) chỉ cấp tool read-only trong `owner_order_only`; Event `2` (`investigator`) gọi `lookup_order` đọc đúng từ DB rằng đơn `O-202` có `status="delivered"`, `delay_days=2` (< 3 ngày, chưa đủ điều kiện hoàn phí ship). Chỉ tới Event `3` agent mới dùng con số `5` trong ticket để ghi đè `delay_days=2` của DB. |
| Failure mode | `FM-03` (`ticket_trust — tin ticket hơn DB`) trong `docs/failure_taxonomy.md` |
| Đối chứng | Cùng `C-002@55` trên shape `fixed`: không có event `model_override`, Event `3` là `quote` (`amount_vnd=0, reason="no_entitlement"`), Event `4` `reply` từ chối, ledger `refund_vnd=0`, `status=denied` (PASS). |
| Regression test | `DbFactKept` (`db_fact_kept` trong `lab9/graders.py` bắt event `model_override`) và `test_public_single_run_cases` (`tests/test_public_matrix.py` cho `C-002@55`); fail trên `swarm` / `seeded_regression` và pass trên `fixed`. |
| Chưa chắc chắn | Một variant khác (`quiet_override`) có thể tin ticket mà không phát ra event `model_override`, nên `DbFactKept` đơn lẻ sẽ không thấy lỗi ở step level mà cần thêm outcome grader (`pass_rate` / `refund_amount_correct`). |

## Quy tắc

- Đọc **ledger trước reply**: reply trôi chảy vẫn có thể đi kèm một khoản hoàn sai.
- "Bước sai đầu tiên" phải dẫn số event cụ thể, không phải "agent bị nhầm".
- Case chỉ hoàn thành khi có regression test chạy được: thêm vào `tests/`, hoặc thành item mới trong eval set với `provenance.from_trace`.
