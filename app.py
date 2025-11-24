import os
import re
import tempfile
import google.generativeai as genai
from datetime import datetime
import pandas as pd
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_mail import Mail, Message   # nếu dùng mail
from flask import session
from werkzeug.security import generate_password_hash, check_password_hash
from flask import jsonify 

# --- IMPORT HỆ THỐNG GỢI Ý (AI.py) CỦA ANH ---
try:
    from AI import get_hotel_recommendations
    print("Tải thành công AI.py (Hệ thống gợi ý)")
except ImportError:
    print("LỖI: Không thể import 'get_hotel_recommendations' từ AI.py.")
    print("Hãy đảm bảo file AI.py nằm cùng thư mục với app.py")
    # Tạo hàm giả để code không bị crash
    def get_hotel_recommendations(input_date_str, input_weather_condition):
        print("LỖI: Đang dùng hàm get_hotel_recommendations() GIẢ.")
        return pd.DataFrame(columns=['name', 'recommend_score'])
# ----------------------------------------------
# -------------------------
# Tạo app Flask
# -------------------------
app = Flask(__name__)
app.secret_key = "your_secret_key_here"

# ...
# ------------------------
# CẤU HÌNH GEMINI API
# ------------------------
try:
    GEMINI_API_KEY = os.environ.get("GOOGLE_API_KEY", "DÁN_GEMINI_API_KEY_CỦA_ANH_VÀO_ĐÂY")
    if not GEMINI_API_KEY or GEMINI_API_KEY == "DÁN_GEMINI_API_KEY_CỦA_ANH_VÀO_ĐÂY":
        print("CẢNH BÁO: GOOGLE_API_KEY chưa được set.")
    
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-2.5-flash')
except Exception as e:
    print(f"Lỗi khởi tạo Gemini: {e}")
    model = None # Đặt là None để kiểm tra sau
# ------------------------

# ... (các dòng định nghĩa USER DATABASE, HÀM HỖ TRỢ... của anh)
# -------------------------
# USER DATABASE (tạm thời dict)
# -------------------------
users_db = {}

# -------------------------
# HÀM HỖ TRỢ
# -------------------------
def get_user_rank(total_spent):
    if total_spent >= 20_000_000:
        return "Bạch kim"
    elif total_spent >= 8_000_000:
        return "Vàng"
    elif total_spent >= 3_000_000:
        return "Bạc"
    else:
        return "Đồng"

def get_discounted_price(rank, base_price):
    discount = {"Đồng": 0, "Bạc": 0.05, "Vàng": 0.1, "Bạch kim": 0.2}
    return int(base_price * (1 - discount.get(rank, 0)))

# -------------------------
# ROUTES
# -------------------------

# AI
@app.route('/ai_chat')
def ai_chat():
    return render_template('ai_chat_hotel.html')

@app.route('/api/firebase-config')
def firebase_config():
    return jsonify({
        "apiKey": "your-api-key",
        "authDomain": "your-project.firebaseapp.com",
        "projectId": "your-project-id"
    })

# Trang chủ + danh sách khách sạn
@app.route("/")
def index():
    hotels = [
        {"name": "Hotel A", "city": "Đà Nẵng", "price": 3000000},
        {"name": "Hotel B", "city": "Hà Nội", "price": 1500000},
        {"name": "Hotel C", "city": "Hồ Chí Minh", "price": 5000000},
    ]
    user_rank = session.get("user_rank", "Đồng")
    for h in hotels:
        h["price_after_discount"] = get_discounted_price(user_rank, h["price"])
    return render_template("index.html", hotels=hotels, user_rank=user_rank)

# Đăng ký
@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        username = request.form["username"].strip()
        if username in users_db:
            flash("Tài khoản đã tồn tại!", "danger")
            return redirect(url_for("register"))

        users_db[username] = {
            "password": generate_password_hash(request.form["password"]),
            "full_name": request.form.get("fullname", ""),
            "dob": request.form.get("birthdate", ""),
            "gender": request.form.get("gender", ""),
            "email": request.form.get("email", ""),
            "phone": request.form.get("phone", ""),
            "total_spent": 0,
            "history": []
        }
        flash("Đăng ký thành công! Hãy đăng nhập.", "success")
        return redirect(url_for("login"))
    return render_template("register.html")

# Đăng nhập
@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]
        user = users_db.get(username)
        if user and check_password_hash(user["password"], password):
            session["user"] = username
            session["user_rank"] = get_user_rank(user["total_spent"])
            flash("Đăng nhập thành công!", "success")
            return redirect(url_for("profile"))
        flash("Sai tài khoản hoặc mật khẩu!", "danger")
        return redirect(url_for("login"))
    return render_template("login.html")

# Đăng xuất
@app.route("/logout")
def logout():
    session.clear()
    flash("Đã đăng xuất!", "success")
    return redirect(url_for("index"))

# Trang cá nhân
@app.route("/profile")
def profile():
    if "user" not in session:
        flash("Bạn cần đăng nhập để xem thông tin.", "danger")
        return redirect(url_for("login"))

    username = session["user"]
    user = users_db[username]

    # Tính tuổi từ dob
    dob = user.get("dob","")
    age = "-"
    if dob:
        birth = datetime.strptime(dob, "%Y-%m-%d")
        age = int((datetime.now() - birth).days / 365.25)

    return render_template("profile.html", user=user, age=age, user_rank=session.get("user_rank","Đồng"))

# Đặt phòng
@app.route("/book/<hotel_name>/<int:price>", methods=["POST"])
def book(hotel_name, price):
    if "user" not in session:
        flash("Bạn cần đăng nhập để đặt phòng.", "danger")
        return redirect(url_for("login"))

    username = session["user"]
    users_db[username]["total_spent"] += price
    users_db[username]["history"].append({
        "name": hotel_name,
        "price": price,
        "date": datetime.now().strftime("%Y-%m-%d %H:%M")
    })
    session["user_rank"] = get_user_rank(users_db[username]["total_spent"])
    flash(f"Đặt phòng {hotel_name} thành công! Giá: {price} VND", "success")
    return redirect(url_for("index"))

# ========================================



# === Hàm lấy dữ liệu ảnh khách sạn (đã có sẵn trong code bạn) ===
def get_hotel_gallery(hotel_name):
    folder_path = os.path.join("static", "images", "hotels", hotel_name)
    if not os.path.exists(folder_path):
        return []
    files = os.listdir(folder_path)
    return [
        f"/static/images/hotels/{hotel_name}/{f}"
        for f in files if f.lower() not in ["main.jng", "main.png"]
    ]
# Hàm đọc bài giới thiệu từ folder static/text/giới_thiệu
def read_intro(city_name):
    """
    city_name: tên chuẩn, ví dụ 'Hà Nội', 'TP Hồ Chí Minh', 'Đà Nẵng', 'Nha Trang'
    """
    # map city name -> tên file
    file_map = {
        "Hà Nội": "hanoi.txt",
        "TP Hồ Chí Minh": "hochiminh.txt",
        "Đà Nẵng": "danang.txt",
        "Nha Trang": "nhatrang.txt"
    }

    filename = file_map.get(city_name)
    if not filename:
        return "❌ Chưa có bài giới thiệu cho địa danh này."

    folder_path = os.path.join("static", "text", "giới thiệu")
    file_path = os.path.join(folder_path, filename)

    if not os.path.exists(file_path):
        return "❌ File giới thiệu chưa được tạo."

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    return content

# Thêm hàm đọc events
def read_events():
    try:
        events_path = os.path.join(DATA_FOLDER, 'events.csv')
        if os.path.exists(events_path):
            return pd.read_csv(events_path, encoding='utf-8-sig')
        return pd.DataFrame()
    except Exception as e:
        print(f"Lỗi đọc events: {e}")
        return pd.DataFrame()

@app.route("/destinations/<city>")
def destination(city):
    city = city.replace("%20", " ").strip()

    # Dữ liệu các địa danh
    data = {
        "Ha Noi": {"name": "Hà Nội", "desc": "...", "image": "/static/images/destinations/cities/hanoi.png"},
        "Ho Chi Minh": {"name": "TP Hồ Chí Minh", "desc": "...", "image": "/static/images/destinations/cities/hcm.png"},
        "Da Nang": {"name": "Đà Nẵng", "desc": "...", "image": "/static/images/destinations/cities/danang.png"},
        "Nha Trang": {"name": "Nha Trang", "desc": "...", "image": "/static/images/destinations/cities/nhatrang.png"}
    }

    key_map = {
        "hanoi": "Ha Noi",
        "danang": "Da Nang",
        "nhatrang": "Nha Trang",
        "hochiminh": "Ho Chi Minh"
    }

    city_key = data.get(city) or data.get(key_map.get(city.lower(), ""), None)
    if not city_key:
        return "❌ Không tìm thấy địa điểm này", 404

    info = city_key
    # đọc bài giới thiệu
    info["intro"] = read_intro(info["name"])

    return render_template("destination.html", info=info)

# -------------------------
# ĐƯỜNG DẪN FILE (LINH HOẠT)
# -------------------------
# Nếu user để hotels.csv cùng thư mục với app.py thì dùng file đó,
# nếu không thì fallback sang thư mục data/.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FOLDER = os.path.join(BASE_DIR, 'data')
os.makedirs(DATA_FOLDER, exist_ok=True)

# ưu tiên file trong cùng thư mục với app.py (nếu tồn tại)
hotels_candidate = os.path.join(BASE_DIR, 'hotels.csv')
if os.path.exists(hotels_candidate):
    HOTELS_CSV = hotels_candidate
else:
    HOTELS_CSV = os.path.join(DATA_FOLDER, 'hotels.csv')

# bookings luôn dùng trong data (nếu bạn muốn khác có thể đổi)
BOOKINGS_CSV = os.path.join(DATA_FOLDER, 'bookings.csv')
REVIEWS_CSV = os.path.join(BASE_DIR, 'reviews.csv') if os.path.exists(os.path.join(BASE_DIR, 'reviews.csv')) else os.path.join(DATA_FOLDER, 'reviews.csv')

# === CẤU HÌNH EMAIL (giữ nguyên) ===
app.config.update(
    MAIL_SERVER='smtp.gmail.com',
    MAIL_PORT=587,
    MAIL_USE_TLS=True,
    MAIL_USE_SSL=False,
    MAIL_USERNAME='hotelpinder@gmail.com',   # Gmail thật
    MAIL_PASSWORD='znsj ynpd burr tdeo',     # Mật khẩu ứng dụng 16 ký tự (giữ như cũ)
    MAIL_DEFAULT_SENDER=('Hotel Pinder', 'hotelpinder@gmail.com')
)
mail = Mail(app)

# === FILE PATHS (Tạo bookings nếu chưa có) ===
try:
    safe_dir = os.path.dirname(BOOKINGS_CSV)
    os.makedirs(safe_dir, exist_ok=True)
    if not os.path.exists(BOOKINGS_CSV):
        df_empty = pd.DataFrame(columns=[
                "hotel_name", "room_type", "price", "user_name", "phone", "email",
                "num_adults", "num_children", "checkin_date", "nights",
                "special_requests", "booking_time", "status"
        ])
        df_empty.to_csv(BOOKINGS_CSV, index=False, encoding="utf-8-sig")
except Exception as e:
    temp_dir = tempfile.gettempdir()
    BOOKINGS_CSV = os.path.join(temp_dir, "bookings.csv")
    print(f"[⚠] Không thể ghi vào thư mục chính, dùng tạm: {BOOKINGS_CSV}")

# === ĐẢM BẢO FILE hotels/reviews (nếu không có thì báo) ===
if not os.path.exists(HOTELS_CSV):
    # nếu không có hotels.csv ở BASE_DIR hoặc data, báo lỗi để user bổ sung
    raise FileNotFoundError(f"❌ Không tìm thấy hotels.csv — đặt file ở: {HOTELS_CSV}")

if not os.path.exists(REVIEWS_CSV):
    pd.DataFrame(columns=["hotel_name", "user", "rating", "comment"]).to_csv(
        REVIEWS_CSV, index=False, encoding="utf-8-sig"
    )

# === HÀM ĐỌC CSV AN TOÀN (sửa để xử lý '5.0', dấu phẩy, v.v.) ===
def read_csv_safe(file_path):
    encodings = ["utf-8-sig", "utf-8", "cp1252"]
    for enc in encodings:
        try:
            # đọc tất cả cột dưới dạng str trước, sau đó convert numeric an toàn
            df = pd.read_csv(file_path, encoding=enc, dtype=str)
            df.columns = df.columns.str.strip()
            # các cột cần convert số
            numeric_cols = ['price', 'stars', 'rating', 'num_adults', 'num_children', 'nights', 'rooms_available']
            for col in numeric_cols:
                if col in df.columns:
                    # loại dấu phẩy, loại ".0" cuối, rồi convert numeric
                    df[col] = df[col].astype(str).str.replace(',', '').str.strip()
                    df[col] = df[col].str.replace(r'\.0$', '', regex=True)  # '5.0' -> '5'
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            return df
        except UnicodeDecodeError:
            continue
        except Exception as e:
            print(f"⚠️ Lỗi khi xử lý file {file_path}: {e}")
            raise
    raise UnicodeDecodeError(f"Không đọc được file {file_path} với UTF-8 hoặc cp1252!")

# === LOAD DỮ LIỆU BAN ĐẦU (vẫn load để có cấu trúc, nhưng routes đọc file tươi) ===
hotels = read_csv_safe(HOTELS_CSV)
reviews_df = read_csv_safe(REVIEWS_CSV)

if 'name' not in hotels.columns:
    if 'Name' in hotels.columns:
        hotels = hotels.rename(columns={'Name': 'name'})
    else:
        raise KeyError("❌ hotels.csv không có cột 'name'!")

if 'hotel_name' not in reviews_df.columns:
    raise KeyError("❌ reviews.csv không có cột 'hotel_name'.")


# === HÀM HỖ TRỢ MAPPING / ICON ===
def yes_no_icon(val):
    return "✅" if str(val).lower() in ("true", "1", "yes") else "❌"

def map_hotel_row(row):
    h = dict(row)
    h["image"] = h.get("image_url", h.get("image", ""))
    html_desc = h.get("review") or h.get("description") or ""
    h["full_desc"] = html_desc
    clean = re.sub(r'<[^>]*>', '', html_desc)
    h["short_desc"] = clean[:150] + ("..." if len(clean) > 150 else "")
    h["gym"] = h.get("gym", False)
    h["spa"] = h.get("spa", False)
    h["sea_view"] = h.get("sea") if "sea" in h else h.get("sea_view", False)
    return h


# === TRANG CHỦ ===
@app.route('/')
def home():
    hotels_df = read_csv_safe(HOTELS_CSV)
    # đảm bảo cột rooms_available và status tồn tại và đúng kiểu
    if 'rooms_available' not in hotels_df.columns:
        hotels_df['rooms_available'] = 0
    hotels_df['rooms_available'] = hotels_df['rooms_available'].astype(int)
    if 'status' not in hotels_df.columns:
        hotels_df['status'] = hotels_df['rooms_available'].apply(lambda x: 'còn' if int(x) > 0 else 'hết')

    cities = sorted(hotels_df['city'].dropna().unique())
    return render_template('index.html', cities=cities)


# === TRANG GỢI Ý / FILTER NÂNG CAO ===
@app.route('/recommend', methods=['POST', 'GET'])
def recommend():
    filtered = read_csv_safe(HOTELS_CSV)

    # đảm bảo cột status và rooms_available tồn tại và đúng kiểu
    if 'rooms_available' not in filtered.columns:
        filtered['rooms_available'] = 0
    filtered['rooms_available'] = filtered['rooms_available'].astype(int)
    if 'status' not in filtered.columns:
        filtered['status'] = filtered['rooms_available'].apply(lambda x: 'còn' if x > 0 else 'hết')
    else:
        filtered['status'] = filtered['rooms_available'].apply(lambda x: 'còn' if x > 0 else 'hết')

    # --- Lấy dữ liệu từ form (POST) hoặc query string (GET) ---
    if request.method == 'POST':
        city = request.form.get('location', '').lower()
        budget = request.form.get('budget', '')
        stars = request.form.get('stars', '')
        amenities = request.form.getlist('amenities')  # danh sách checkbox
        size = request.form.get('size', '')
    else:
        city = request.args.get('location', '').lower()
        budget = request.args.get('budget', '')
        stars = request.args.get('stars', '')
        amenities = request.args.getlist('amenities')
        size = request.args.get('size', '')

    # --- Lọc theo thành phố ---
    if city:
        filtered = filtered[filtered['city'].str.lower() == city]

    # --- Lọc theo ngân sách ---
    if budget:
        try:
            budget = float(budget)
            filtered = filtered[filtered['price'] <= budget]
        except Exception:
            pass

    # --- Lọc theo số sao ---
    if stars:
        try:
            stars = int(stars)
            filtered = filtered[filtered['stars'] >= stars]
        except Exception:
            pass

    # --- Lọc theo tiện nghi ---
    for amen in amenities:
        if amen == 'pool':
            filtered = filtered[filtered['pool'] == True]
        elif amen == 'sea':
            filtered = filtered[(filtered.get('sea', False) == True) | (filtered.get('sea_view', False) == True)]
        elif amen == 'breakfast':
            filtered = filtered[filtered['buffet'] == True]
        elif amen == 'bar':
            filtered = filtered[filtered['bar'] == True]

    # --- Lọc theo loại phòng (diện tích) ---
    if size:
        def room_size_ok(row):
            try:
                s = float(row.get('size', 0))
            except:
                s = 0
            if size == 'small':
                return s < 25
            elif size == 'medium':
                return 25 <= s <= 40
            elif size == 'large':
                return s > 40
            return True
        filtered = filtered[filtered.apply(room_size_ok, axis=1)]

    # --- Chuẩn bị kết quả ---
    results = [map_hotel_row(r) for r in filtered.to_dict(orient='records')]

    return render_template('result.html', hotels=results)


# === TRANG CHI TIẾT ===
@app.route('/hotel/<name>')
def hotel_detail(name):
    hotels_df = read_csv_safe(HOTELS_CSV)

    if 'rooms_available' not in hotels_df.columns:
        hotels_df['rooms_available'] = 0
    hotels_df['rooms_available'] = hotels_df['rooms_available'].astype(int)
    if 'status' not in hotels_df.columns:
        hotels_df['status'] = hotels_df['rooms_available'].apply(lambda x: 'còn' if int(x) > 0 else 'hết')
    else:
        hotels_df['status'] = hotels_df['rooms_available'].apply(lambda x: 'còn' if int(x) > 0 else 'hết')

    hotel_data = hotels_df[hotels_df['name'] == name]

    if hotel_data.empty:
        return "<h3>Không tìm thấy khách sạn!</h3>", 404

    hotel = map_hotel_row(hotel_data.iloc[0].to_dict())
    reviews_df_local = read_csv_safe(REVIEWS_CSV)
    hotel_reviews = reviews_df_local[reviews_df_local['hotel_name'] == name].to_dict(orient='records')

    avg_rating = (
        round(sum(float(r.get('rating', 0)) for r in hotel_reviews) / len(hotel_reviews), 1)
        if hotel_reviews else hotel.get('rating', 'Chưa có')
    )

    features = {
        "Buffet": yes_no_icon(hotel.get("buffet")),
        "Bể bơi": yes_no_icon(hotel.get("pool")),
        "Gần biển": yes_no_icon(hotel.get("sea_view") or hotel.get("sea")),
        "View biển": yes_no_icon(hotel.get("view")),
    }

    rooms = [
        {"type": "Phòng nhỏ", "price": round(float(hotel.get('price', 0)) * 1.0)},
        {"type": "Phòng đôi", "price": round(float(hotel.get('price', 0)) * 1.5)},
        {"type": "Phòng tổng thống", "price": round(float(hotel.get('price', 0)) * 2.5)},
    ]

    # === THÊM GALLERY VÀO KHÁCH SẠN ===
    hotel['gallery'] = get_hotel_gallery(hotel['name'])

    return render_template(
        'detail.html',
        hotel=hotel,
        features=features,
        rooms=rooms,
        reviews=hotel_reviews,
        avg_rating=avg_rating
    )

# === GỬI ĐÁNH GIÁ ===
@app.route('/review/<name>', methods=['POST'])
def add_review(name):
    user = request.form.get('user', 'Ẩn danh').strip()
    rating = int(request.form.get('rating', 0))
    comment = request.form.get('comment', '').strip()

    new_review = pd.DataFrame([{
        "hotel_name": name,
        "user": user,
        "rating": rating,
        "comment": comment
    }])

    df = read_csv_safe(REVIEWS_CSV)
    df = pd.concat([df, new_review], ignore_index=True)
    df.to_csv(REVIEWS_CSV, index=False, encoding="utf-8-sig")

    return redirect(url_for('hotel_detail', name=name))

# === TRANG ĐẶT PHÒNG ===
@app.route('/booking/<name>/<room_type>', methods=['GET', 'POST'])
def booking(name, room_type):
    hotels_df = read_csv_safe(HOTELS_CSV)
    if 'rooms_available' not in hotels_df.columns:
        hotels_df['rooms_available'] = 0
    hotels_df['rooms_available'] = hotels_df['rooms_available'].astype(int)
    if 'status' not in hotels_df.columns:
        hotels_df['status'] = hotels_df['rooms_available'].apply(lambda x: 'còn' if int(x) > 0 else 'hết')
    else:
        hotels_df['status'] = hotels_df['rooms_available'].apply(lambda x: 'còn' if int(x) > 0 else 'hết')

    hotel_data = hotels_df[hotels_df['name'] == name]

    if hotel_data.empty:
        return "<h3>Không tìm thấy khách sạn!</h3>", 404

    hotel = map_hotel_row(hotel_data.iloc[0].to_dict())

    # --- 🟢 LẤY STATUS MỚI NHẤT TỪ CSV ---
    hotel_row = hotels_df[hotels_df['name'] == name].iloc[0]
    hotel['status'] = 'còn' if int(hotel_row['rooms_available']) > 0 else 'hết'
    is_available = hotel['status'].lower() == 'còn'
    flash(f"Trạng thái phòng hiện tại: {hotel['status']}", "info")

    # --- 🛑 Kiểm tra trạng thái phòng ---
    if not is_available:
        flash("Khách sạn này hiện đã hết phòng. Vui lòng chọn khách sạn khác.", "danger")
        #return redirect(url_for('home'))  # chuyển về trang chủ

    # Xử lý POST đặt phòng
    if request.method == 'POST':
        info = {
            "hotel_name": name,
            "room_type": room_type,
            "price": float(request.form.get('price', hotel.get('price', 0))),
            "user_name": request.form['fullname'].strip(),
            "phone": request.form['phone'].strip(),
            "email": request.form.get('email', '').strip(),
            "num_adults": max(int(request.form.get('adults', 1)), 1),
            "num_children": max(int(request.form.get('children', 0)), 0),
            "checkin_date": request.form['checkin'],
            "nights": 1,
            "special_requests": request.form.get('note', '').strip(),
            "booking_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "status": "Chờ xác nhận"
        }

        # Ghi CSV đặt phòng
        try:
            df = pd.read_csv(BOOKINGS_CSV, encoding="utf-8-sig")
        except FileNotFoundError:
            df = pd.DataFrame(columns=info.keys())
        df = pd.concat([df, pd.DataFrame([info])], ignore_index=True)
        df.to_csv(BOOKINGS_CSV, index=False, encoding="utf-8-sig")

        # Gửi email khách
        if info["email"]:
            try:
                msg_user = Message(
                    subject="Xác nhận đặt phòng - Hotel Pinder",
                    recipients=[info["email"]]
                )
                msg_user.html = f"""..."""  # giữ nguyên nội dung email
                mail.send(msg_user)
            except Exception as e:
                print(f"⚠️ Lỗi gửi email cho khách: {e}")

        # Gửi email admin
        try:
            msg_admin = Message(
                subject=f"🔔 Đơn đặt phòng mới tại {info['hotel_name']}",
                recipients=["hotelpinder@gmail.com"]
            )
            msg_admin.html = f"""..."""  # giữ nguyên nội dung email admin
            mail.send(msg_admin)
        except Exception as e:
            print(f"⚠️ Lỗi gửi email admin: {e}")

        return render_template('success.html', info=info)

    return render_template('booking.html', hotel=hotel, room_type=room_type, is_available=is_available)



# === LỊCH SỬ ĐẶT PHÒNG ===
@app.route('/history', methods=['GET', 'POST'])
def booking_history():
    bookings = []
    email = ""

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        if os.path.exists(BOOKINGS_CSV) and email:
            df = pd.read_csv(BOOKINGS_CSV, encoding='utf-8-sig')
            df['email'] = df['email'].astype(str).str.lower()
            bookings = df[df['email'] == email].to_dict(orient='records')

    return render_template('history.html', bookings=bookings, email=email)


# === TRANG GIỚI THIỆU ===
@app.route('/about')
def about_page():
    return render_template('about.html')

# === ĐĂNG NHẬP QUẢN TRỊ ===
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        # ⚙️ Tài khoản admin cố định (có thể sửa)
        if username == "admin" and password == "123456":
            session['admin'] = True
            flash("Đăng nhập thành công!", "success")
            return redirect(url_for('admin_dashboard'))
        else:
            flash("Sai tài khoản hoặc mật khẩu!", "danger")
    return render_template('admin_login.html')


# === ĐĂNG XUẤT ===
@app.route('/admin/logout')
def admin_logout():
    session.pop('admin', None)
    flash("Đã đăng xuất!", "info")
    return redirect(url_for('admin_login'))


# === TRANG DASHBOARD QUẢN TRỊ ===
@app.route('/admin')
def admin_dashboard():
    if not session.get('admin'):
        return redirect(url_for('admin_login'))

    # Đọc dữ liệu
    hotels_df = pd.read_csv(HOTELS_CSV, encoding='utf-8-sig')
    bookings_df = pd.read_csv(BOOKINGS_CSV, encoding='utf-8-sig') if os.path.exists(BOOKINGS_CSV) else pd.DataFrame()

    total_hotels = len(hotels_df)
    total_bookings = len(bookings_df)
    total_cities = hotels_df['city'].nunique()

    return render_template('admin_dashboard.html',
                           total_hotels=total_hotels,
                           total_bookings=total_bookings,
                           total_cities=total_cities)


@app.route('/admin/hotels', methods=['GET', 'POST'])
def admin_hotels():
    if not session.get('admin'):
        return redirect(url_for('admin_login'))

    # Đọc file khách sạn
    df = pd.read_csv(HOTELS_CSV, encoding='utf-8-sig')

    # --- Đảm bảo các cột cần thiết có tồn tại ---
    if 'rooms_available' not in df.columns:
        df['rooms_available'] = 1
    if 'status' not in df.columns:
        df['status'] = 'còn'

    # --- Xử lý dữ liệu bị thiếu hoặc NaN ---
    # Chuyển kiểu an toàn (loại '5.0' -> '5', loại dấu phẩy)
    df['rooms_available'] = df['rooms_available'].astype(str).str.replace(',', '').str.strip()
    df['rooms_available'] = df['rooms_available'].str.replace(r'\.0$', '', regex=True)
    df['rooms_available'] = pd.to_numeric(df['rooms_available'], errors='coerce').fillna(0).astype(int)
    df['status'] = df['rooms_available'].apply(lambda x: 'còn' if x > 0 else 'hết')
    df.to_csv(HOTELS_CSV, index=False, encoding='utf-8-sig')


    # --- Thêm khách sạn mới ---
    if request.method == 'POST' and 'name' in request.form and 'add_hotel' not in request.form:
        name = request.form.get('name', '').strip()
        city = request.form.get('city', '').strip()
        price = request.form.get('price', '').strip()
        stars = request.form.get('stars', '').strip()
        description = request.form.get('description', '').strip()
        rooms_available = request.form.get('rooms_available', 1)

        try:
            rooms_available = int(float(str(rooms_available).replace(',', '').replace('.0', '')))
        except Exception:
            rooms_available = 1

        if name and city:
            new_row = {
                "name": name,
                "city": city,
                "price": price,
                "stars": stars,
                "description": description,
                "rooms_available": rooms_available,
                "status": "còn" if rooms_available > 0 else "hết"
            }
            df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
            df.to_csv(HOTELS_CSV, index=False, encoding='utf-8-sig')
            flash("✅ Đã thêm khách sạn mới!", "success")
            return redirect(url_for('admin_hotels'))
        else:
            flash("⚠️ Tên và thành phố không được để trống!", "warning")

    # --- Cập nhật số phòng còn ---
    if request.method == 'POST' and 'update_hotel' in request.form:
        update_name = request.form.get('update_name', '').strip()
        update_rooms = request.form.get('update_rooms', '').strip()

        try:
            update_rooms = int(float(str(update_rooms).replace(',', '').replace('.0', '')))
        except ValueError:
            update_rooms = 0

        if update_name in df['name'].values:
            df.loc[df['name'] == update_name, 'rooms_available'] = update_rooms
            df.loc[df['name'] == update_name, 'status'] = 'còn' if update_rooms > 0 else 'hết'
            df.to_csv(HOTELS_CSV, index=False, encoding='utf-8-sig')
            flash(f"🔧 Đã cập nhật số phòng cho {update_name}", "success")
        else:
            flash("⚠️ Không tìm thấy khách sạn có tên này!", "danger")

    hotels = df.to_dict(orient='records')
    return render_template('admin_hotels.html', hotels=hotels)


# === Quản lý đặt phòng (Admin) ===
@app.route('/admin/bookings')
def admin_bookings():
    if not session.get('admin'):
        return redirect(url_for('admin_login'))

    if os.path.exists(BOOKINGS_CSV):
        df = pd.read_csv(BOOKINGS_CSV, encoding='utf-8-sig')
        bookings = df.to_dict(orient='records')
    else:
        bookings = []

    return render_template('admin_bookings.html', bookings=bookings)


# === Xác nhận đặt phòng ===
@app.route('/admin/bookings/confirm/<booking_time>')
def admin_confirm_booking(booking_time):
    if not session.get('admin'):
        return redirect(url_for('admin_login'))

    df = pd.read_csv(BOOKINGS_CSV, encoding='utf-8-sig')
    df.loc[df['booking_time'] == booking_time, 'status'] = 'Đã xác nhận'
    df.to_csv(BOOKINGS_CSV, index=False, encoding='utf-8-sig')
    flash("Đã xác nhận đặt phòng!", "success")
    return redirect(url_for('admin_bookings'))


# === Xóa đặt phòng ===
@app.route('/admin/bookings/delete/<booking_time>')
def admin_delete_booking(booking_time):
    if not session.get('admin'):
        return redirect(url_for('admin_login'))

    df = pd.read_csv(BOOKINGS_CSV, encoding='utf-8-sig')
    df = df[df['booking_time'] != booking_time]
    df.to_csv(BOOKINGS_CSV, index=False, encoding='utf-8-sig')
    flash("Đã xóa đặt phòng!", "info")
    return redirect(url_for('admin_bookings'))


# === XÓA KHÁCH SẠN ===
@app.route('/admin/hotels/delete/<name>')
def delete_hotel(name):
    if not session.get('admin'):
        return redirect(url_for('admin_login'))
    try:
        df = pd.read_csv(HOTELS_CSV, encoding='utf-8-sig')
        df = df[df['name'] != name]
        df.to_csv(HOTELS_CSV, index=False, encoding='utf-8-sig')
        flash(f"Đã xóa khách sạn: {name}", "info")
    except Exception as e:
        flash(f"Lỗi khi xóa khách sạn: {e}", "danger")
    return redirect(url_for('admin_hotels'))

#  TẠO "CẦU NỐI" (API ENDPOINT) CHO AI CHAT
@app.route('/api/chat', methods=['POST'])
def api_chat():
    if not model:
        return jsonify({"error": "Gemini AI chưa được cấu hình"}), 500
        
    try:
        user_query = request.json.get('query')
        include_hotels = request.json.get('include_hotels', True)
        
        if not user_query:
            return jsonify({"error": "Missing query"}), 400

        # 1. Đọc và xử lý dữ liệu từ CSV
        hotels_data = []
        reviews_data = []
        events_data = []
        
        try:
            # Đọc hotels.csv
            hotels_df = pd.read_csv("hotels.csv", encoding='utf-8-sig')
            for _, hotel in hotels_df.iterrows():
                hotel_info = {
                    'name': hotel.get('name', ''),
                    'city': hotel.get('city', ''),
                    'district': hotel.get('district', 'Trung tâm'),
                    'price': hotel.get('price', 'Liên hệ'),
                    'rating': hotel.get('rating', 4.0),
                    'amenities': hotel.get('amenities', 'WiFi, Restaurant, Pool'),
                    'description': hotel.get('description', 'Khách sạn chất lượng với đầy đủ tiện ích')
                }
                hotels_data.append(hotel_info)
            
            # Đọc reviews.csv
            reviews_df = pd.read_csv("reviews.csv", encoding='utf-8-sig')
            for _, review in reviews_df.iterrows():
                review_info = {
                    'hotel_name': review.get('hotel_name', ''),
                    'user': review.get('user', 'Khách hàng'),
                    'rating': review.get('rating', 4.5),
                    'comment': review.get('comment', 'Trải nghiệm tuyệt vời!')
                }
                reviews_data.append(review_info)
            
            # Đọc events.csv
            events_df = pd.read_csv("events.csv", encoding='utf-8-sig')
            for _, event in events_df.iterrows():
                event_info = {
                    'event_name': event.get('event_name', ''),
                    'city': event.get('city', ''),
                    'start_date': event.get('start_date', ''),
                    'end_date': event.get('end_date', ''),
                    'season': event.get('season', 'Không xác định')
                }
                events_data.append(event_info)
                
        except Exception as e:
            print(f"Lỗi đọc CSV: {e}")
            # Fallback data với các khách sạn mẫu
            hotels_data = [
                {
                    'name': 'Sunrise Nha Trang',
                    'city': 'Nha Trang',
                    'district': 'Trần Phú',
                    'price': '2,500,000 VNĐ',
                    'rating': 4.8,
                    'amenities': 'Pool, Spa, Beach Front, Restaurant, Bar',
                    'description': 'Khách sạn 5 sao view biển tuyệt đẹp với hồ bơi vô cực'
                },
                {
                    'name': 'Mường Thanh Đà Nẵng',
                    'city': 'Đà Nẵng',
                    'district': 'Sơn Trà',
                    'price': '1,800,000 VNĐ',
                    'rating': 4.5,
                    'amenities': 'Pool, Gym, Restaurant, Kids Club',
                    'description': 'Khách sạn hiện đại gần biển Mỹ Khê'
                },
                {
                    'name': 'Intercontinental Hanoi',
                    'city': 'Hà Nội',
                    'district': 'Ba Đình',
                    'price': '3,500,000 VNĐ',
                    'rating': 4.9,
                    'amenities': 'Spa, Pool, Fine Dining, Bar',
                    'description': 'Khách sạn sang trọng bậc nhất tại trung tâm Hà Nội'
                }
            ]

        # 2. Phân tích câu hỏi để xác định có cần đề xuất khách sạn không
        need_hotel_recommendation = any(keyword in user_query.lower() for keyword in [
            'tìm khách sạn', 'đề xuất khách sạn', 'khách sạn nào', 'ở đâu',
            'tìm chỗ ở', 'booking', 'đặt phòng', 'recommend', 'suggest', 'hotel',
            'nghỉ ở đâu', 'chỗ ở', 'khách sạn', 'resort', 'nhà nghỉ'
        ])

        # 3. Xây dựng prompt thông minh
        system_prompt = f"""
Bạn là trợ lý du lịch THÔNG MINH. 

QUAN TRỌNG: KHI ĐỀ XUẤT KHÁCH SẠN, CHỈ ĐƯỢC DÙNG CÁC KHÁCH SẠN TRONG DANH SÁCH NÀY:

DANH SÁCH KHÁCH SẠN CÓ SẴN:
{get_hotel_names_list(hotels_data)}

QUY TẮC BẮT BUỘC:
1. CHỈ đề xuất khách sạn có tên CHÍNH XÁC trong danh sách trên
2. Mô tả khách sạn dựa trên thông tin thực tế từ danh sách
3. Nếu user yêu cầu khách sạn không có trong danh sách: đề xuất khách sạn TƯƠNG TỰ có sẵn
4. Luôn đề xuất 1-3 khách sạn phù hợp nhất từ danh sách

CÁCH ĐỀ XUẤT:
- So sánh các lựa chọn dựa trên vị trí, giá, tiện ích
- Highlight điểm mạnh của từng khách sạn  
- Đề xuất khách sạn phù hợp với ngân sách và nhu cầu

Hãy trả lời TỰ NHIÊN như một chuyên gia du lịch thực thụ!
"""

        # 4. Gọi Gemini
        max_retries = 2
        for attempt in range(max_retries):
            try:
                response = model.generate_content(
                    system_prompt + "\n\nCâu hỏi của người dùng: " + user_query,
                    generation_config=genai.GenerationConfig(
                        temperature=0.8,
                        max_output_tokens=2000
                    )
                )
                ai_response = response.text
                
                # Clean up response
                cleaned_response = ai_response.replace('**', '').replace('*', '')
                
                # Chuẩn bị dữ liệu khách sạn để trả về
                response_data = {"response": cleaned_response}
                
                # Chỉ trả về hotel data nếu AI thực sự đề xuất khách sạn
                if need_hotel_recommendation and include_hotels:
                    # ĐỒNG BỘ khách sạn với những gì AI đã đề xuất trong response
                    recommended_hotels = sync_hotels_with_ai_response(hotels_data, reviews_data, user_query, cleaned_response)
                    response_data["hotels"] = recommended_hotels[:3]  # Tối đa 3 khách sạn
                
                return jsonify(response_data)
                
            except Exception as e:
                if "quota" in str(e).lower() or "429" in str(e):
                    if attempt < max_retries - 1:
                        wait_time = 2 ** attempt
                        print(f"Quota exceeded, retrying in {wait_time}s...")
                        time.sleep(wait_time)
                        continue
                    else:
                        return jsonify({"error": "Hệ thống đang quá tải. Vui lòng thử lại sau 1 phút."}), 429
                else:
                    raise e

        return jsonify({"error": "Lỗi kết nối. Vui lòng thử lại."}), 500

    except Exception as e:
        print(f"Lỗi API chat: {e}")
        return jsonify({"response": "Hiện tại hệ thống đang gặp sự cố kỹ thuật. Tôi vẫn muốn lắng nghe và hỗ trợ bạn. Hãy thử lại sau ít phút nhé!"})

def clean_ai_response(response, is_first_message=False):
    """Làm sạch response AI, loại bỏ các từ chào hỏi không cần thiết"""
    cleaned = response.replace('**', '').replace('*', '')
    
    # Chỉ giữ lại chào hỏi nếu là tin nhắn đầu tiên
    if not is_first_message:
        # Loại bỏ các cụm chào hỏi thường gặp
        greeting_patterns = [
            r'^(Xin chào|Chào bạn|Hello|Hi)[!.,]?\s*',
            r'^(Cảm ơn bạn|Thanks)[!.,]?\s*',
            r'^(Rất vui|Tôi rất vui)[^.!?]*[.!?]\s*',
            r'^(Tôi xin|Xin được)[^.!?]*[.!?]\s*'
        ]
        
        for pattern in greeting_patterns:
            cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
    
    # Loại bỏ khoảng trắng thừa
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    
    return cleaned

def sync_hotels_with_ai_response(hotels_data, reviews_data, user_query, ai_response):
    """Đồng bộ khách sạn được đề xuất với tên mà AI đã mention trong response"""
    
    # Tìm tên khách sạn được AI đề xuất trong response
    mentioned_hotel_names = []
    
    # Kiểm tra tất cả khách sạn trong database xem có được AI nhắc đến không
    for hotel in hotels_data:
        hotel_name = hotel['name']
        # Tìm tên khách sạn trong response AI (so khớp linh hoạt)
        if (hotel_name.lower() in ai_response.lower() or 
            any(word in ai_response.lower() for word in hotel_name.lower().split())):
            mentioned_hotel_names.append(hotel_name)
    
    print(f"🔍 AI mentioned hotels: {mentioned_hotel_names}")  # Debug log
    
    # Nếu AI có đề cập cụ thể khách sạn nào, ưu tiên những cái đó
    if mentioned_hotel_names:
        filtered_hotels = []
        for hotel_name in mentioned_hotel_names[:3]:  # Lấy tối đa 3 khách sạn đầu
            matching_hotel = next((h for h in hotels_data if h['name'] == hotel_name), None)
            if matching_hotel:
                # Thêm review nếu có
                hotel_reviews = [r for r in reviews_data if r['hotel_name'] == hotel_name]
                if hotel_reviews:
                    matching_hotel['review'] = hotel_reviews[0]
                filtered_hotels.append(matching_hotel)
        
        if filtered_hotels:
            print(f"✅ Using AI-mentioned hotels: {[h['name'] for h in filtered_hotels]}")
            return filtered_hotels
    
    # Fallback: lọc theo query như cũ (chỉ khi AI không đề cập cụ thể khách sạn nào)
    print("🔄 No AI-mentioned hotels found, using query-based filtering")
    return filter_hotels_by_query(hotels_data, reviews_data, user_query)

def filter_hotels_by_query(hotels_data, reviews_data, user_query):
    """Lọc khách sạn phù hợp dựa trên query của người dùng"""
    filtered_hotels = []
    
    query_lower = user_query.lower()
    
    # Xác định thành phố từ query
    target_city = None
    city_keywords = {
        'đà nẵng': 'Đà Nẵng',
        'hà nội': 'Hà Nội', 
        'hồ chí minh': 'Hồ Chí Minh',
        'sài gòn': 'Hồ Chí Minh',
        'nha trang': 'Nha Trang',
        'huế': 'Huế',
        'hội an': 'Hội An'
    }
    
    for keyword, city in city_keywords.items():
        if keyword in query_lower:
            target_city = city
            break
    
    for hotel in hotels_data:
        score = 0
        
        # Ưu tiên cao nhất: khách sạn cùng thành phố
        if target_city and hotel.get('city') == target_city:
            score += 5
            
        # Kiểm tra khu vực/quận
        if 'district' in hotel and any(district in query_lower for district in hotel['district'].lower().split()):
            score += 3
            
        # Kiểm tra tiện ích cụ thể
        if 'amenities' in hotel:
            amenities = hotel['amenities'].lower()
            if 'hồ bơi' in query_lower or 'pool' in query_lower:
                if 'pool' in amenities or 'bơi' in amenities:
                    score += 2
            if 'spa' in query_lower or 'massage' in query_lower:
                if 'spa' in amenities:
                    score += 2
            if 'gym' in query_lower or 'fitness' in query_lower:
                if 'gym' in amenities or 'fitness' in amenities:
                    score += 2
        
        # Kiểm tra loại khách sạn
        if any(keyword in query_lower for keyword in ['sang trọng', 'luxury', '5 sao', 'năm sao', 'cao cấp']):
            if hotel.get('rating', 0) >= 4.5:
                score += 2
        elif any(keyword in query_lower for keyword in ['bình dân', 'budget', 'giá rẻ', 'tiết kiệm']):
            price_str = str(hotel.get('price', '')).lower()
            if any(price_indicator in price_str for price_indicator in ['500', '600', '700', '800', 'triệu']):
                score += 2
                
        # Kiểm tra view/biển
        if any(keyword in query_lower for keyword in ['biển', 'beach', 'view biển', 'sea']):
            hotel_desc = hotel.get('description', '').lower() + hotel.get('amenities', '').lower()
            if any(view_keyword in hotel_desc for view_keyword in ['beach', 'biển', 'sea', 'view biển']):
                score += 2
                
        # Thêm review nếu có
        hotel_reviews = [r for r in reviews_data if r['hotel_name'] == hotel['name']]
        if hotel_reviews:
            hotel['review'] = hotel_reviews[0]
            
        # Chỉ thêm khách sạn có điểm > 0 hoặc query chung chung
        if score > 0 or any(keyword in query_lower for keyword in ['khách sạn', 'đề xuất', 'tìm', 'recommend', 'suggest']):
            hotel['match_score'] = score  # Thêm score để debug
            filtered_hotels.append(hotel)
    
    # Sắp xếp theo điểm match
    filtered_hotels.sort(key=lambda x: x.get('match_score', 0), reverse=True)
    
    # Debug log (ĐÃ SỬA LỖI SYNTAX)
    if filtered_hotels:
        hotel_names = [f"{h['name']} (score: {h.get('match_score', 0)})" for h in filtered_hotels[:3]]
        print(f"🎯 Filtered hotels by query: {hotel_names}")
    else:
        # Fallback: lấy 3 khách sạn có rating cao nhất
        filtered_hotels = sorted(hotels_data, key=lambda x: x.get('rating', 0), reverse=True)[:3]
        print(f"🔄 No matches, using top-rated: {[h['name'] for h in filtered_hotels]}")
    
    return filtered_hotels

def google_search(query):
    """Hàm search web đơn giản"""
    try:
        # Có thể dùng SerpAPI, Google Custom Search API, hoặc search đơn giản
        search_url = f"https://www.google.com/search?q={requests.utils.quote(query + ' site:việt nam')}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(search_url, headers=headers, timeout=10)
        # Đây là ví dụ đơn giản, thực tế cần dùng API chính thức
        
        return f"Đã tìm thấy thông tin về: {query}"
        
    except Exception as e:
        return f"Không thể tìm kiếm thông tin: {str(e)}"

# === CẬP NHẬT TRẠNG THÁI KHÁCH SẠN ===
@app.route('/admin/hotels/status/<name>/<status>')
def update_hotel_status(name, status):
    if not session.get('admin'):
        return redirect(url_for('admin_login'))
    try:
        # --- Đọc CSV trước ---
        df = pd.read_csv(HOTELS_CSV, encoding='utf-8-sig')

        if name in df['name'].values:
            # ✅ Cập nhật trạng thái
            df.loc[df['name'] == name, 'status'] = status

            # ✅ Đồng bộ rooms_available
            if status.strip().lower() == 'còn':
                # Nếu admin set "còn" mà rooms_available = 0 thì tự đặt = 1
                df.loc[df['name'] == name, 'rooms_available'] = df.loc[df['name'] == name, 'rooms_available'].replace(0, 1)
            elif status.strip().lower() == 'hết':
                df.loc[df['name'] == name, 'rooms_available'] = 0

            # Đồng bộ lại status theo rooms_available để hiển thị đúng trên booking
            df['status'] = df['rooms_available'].apply(lambda x: 'còn' if x > 0 else 'hết')

            df.to_csv(HOTELS_CSV, index=False, encoding='utf-8-sig')
            flash(f"✅ Đã cập nhật {name} → {status}", "success")
        else:
            flash("⚠️ Không tìm thấy khách sạn này!", "warning")
    except Exception as e:
        flash(f"Lỗi khi cập nhật trạng thái: {e}", "danger")
    return redirect(url_for('admin_hotels'))


# === KHỞI CHẠY APP ===
if __name__ == '__main__':
    app.run(debug=True)



















