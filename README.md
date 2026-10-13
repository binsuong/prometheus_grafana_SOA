# Hướng dẫn setup Prometheus Grafana SOA

## 1. Chuẩn bị

- Cài Git và Docker Desktop (hoặc Docker Engine có Docker Compose).
- Mở Docker trước khi chạy lệnh. Trên Windows, sử dụng Linux containers.
- Đảm bảo các cổng `8000`, `9090`, `3000` chưa bị sử dụng; cần thêm `4040` nếu chạy ngrok.

Không cần cài Python riêng khi chạy bằng Docker.

## 2. Tải mã nguồn

```sh
git clone https://github.com/binsuong/prometheus_grafana_SOA.git
cd prometheus_grafana_SOA
```

Nếu đã có mã nguồn, mở terminal tại thư mục chứa `docker-compose.yaml`. Chạy các lệnh bên dưới trong thư mục này.

## 3. Tạo file `.env`

**Windows PowerShell:**

```powershell
Copy-Item .env.example .env
```

**macOS/Linux:**

```sh
cp .env.example .env
```

Nếu đã có `.env`, chỉnh sửa file hiện tại thay vì sao chép đè. Điền cấu hình:

```dotenv
NGROK_AUTHTOKEN=
GRAFANA_ACCOUNT=admin
GRAFANA_PASS=thay_bang_mat_khau_cua_ban
```

- `GRAFANA_ACCOUNT`, `GRAFANA_PASS`: tài khoản đăng nhập Grafana khi khởi tạo dữ liệu lần đầu.
- `NGROK_AUTHTOKEN`: để trống nếu chỉ chạy trên máy local; điền authtoken của tài khoản ngrok nếu muốn chia sẻ Grafana qua Internet.

Không chia sẻ hoặc commit file `.env` chứa thông tin đăng nhập.

## 4. Khởi động

**Chạy local, không cần ngrok:**

```sh
docker compose up -d --build app fakeuser prometheus grafana
```

**Hoặc chạy toàn bộ hệ thống, bao gồm ngrok** (cần điền `NGROK_AUTHTOKEN` trước):

```sh
docker compose up -d --build
```

Lần đầu cần chờ Docker tải image và cài thư viện. Sau đó kiểm tra:

```sh
docker compose ps
```

## 5. Truy cập và kiểm tra

| Thành phần | Địa chỉ | Cách kiểm tra |
| --- | --- | --- |
| Ứng dụng | [localhost:8000/healthz](http://localhost:8000/healthz) | Phản hồi `ok`. |
| Metrics | [localhost:8000/metrics](http://localhost:8000/metrics) | Hiển thị dữ liệu metrics dạng văn bản. |
| Prometheus | [localhost:9090/targets](http://localhost:9090/targets) | Chờ khoảng 10–20 giây; target `python-app` và `prometheus` có trạng thái `UP`. |
| Grafana | [localhost:3000](http://localhost:3000) | Đăng nhập bằng `GRAFANA_ACCOUNT` và `GRAFANA_PASS` trong `.env`. |

Grafana đã có cấu hình tự nạp nguồn dữ liệu **Prometheus**. Để kiểm tra, mở **Explore**, chọn nguồn dữ liệu **Prometheus** và chạy truy vấn `up{job="python-app"}`; kết quả mong đợi là `1`.

File `grafana/dashboards/demo.json` hiện đang trống nên chưa có dashboard mẫu để mở. Bạn có thể tạo dashboard trong Grafana hoặc bổ sung file JSON dashboard hợp lệ vào đường dẫn này. Bộ `fakeuser` tự tạo lưu lượng; chờ 1–2 phút nếu truy vấn metrics chưa có dữ liệu.

Nếu bật ngrok, tunnel hiện trỏ tới Grafana. Xem trạng thái và thông tin kết nối bằng:

```sh
docker compose logs --tail=100 ngrok
```

Sử dụng URL public do ngrok cung cấp để truy cập Grafana từ bên ngoài, rồi đăng nhập bằng tài khoản đã cấu hình.

## 6. Dừng và chạy lại

```sh
# Dừng hệ thống, giữ dữ liệu Prometheus và Grafana
docker compose down

# Chạy lại trên máy local
docker compose up -d --build app fakeuser prometheus grafana
```

Nếu muốn chạy lại cùng ngrok, dùng `docker compose up -d --build`.

## 7. Khi setup gặp lỗi

- **Không kết nối được Docker:** mở Docker Desktop hoặc khởi động Docker Engine.
- **Cổng bị chiếm:** dừng ứng dụng đang dùng cổng hoặc đổi cổng bên trái trong `ports` của `docker-compose.yaml`, ví dụ `"3001:3000"` để truy cập Grafana tại `localhost:3001`.
- **ngrok báo lỗi xác thực:** kiểm tra `NGROK_AUTHTOKEN` trong `.env`, sau đó chạy `docker compose up -d ngrok`.
- **Grafana không nhận mật khẩu mới trong `.env`:** biến môi trường chỉ tạo tài khoản ban đầu; nếu đã có dữ liệu Grafana, đăng nhập bằng mật khẩu đã thiết lập trước đó.
- **Truy vấn chưa có dữ liệu:** kiểm tra target Prometheus là `UP`, `fakeuser` đang chạy và chờ thêm vài chu kỳ thu thập.

Xem log để xác định service gặp lỗi:

```sh
docker compose logs --tail=100 app fakeuser prometheus grafana
```
