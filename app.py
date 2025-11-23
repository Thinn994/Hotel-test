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
        if not user_query:
            return jsonify({"error": "Missing query"}), 400

        # 1. Đọc dữ liệu từ CSV
        try:
            hotels_df = pd.read_csv("hotels.csv", encoding='utf-8-sig')
            
            # Format hotels info đơn giản hơn - CHỈ TÊN & THÀNH PHỐ
            hotels_list = []
            for _, hotel in hotels_df.iterrows():
                hotels_list.append(f"{hotel['name']} ({hotel['city']})")
            hotels_info = "\n".join(hotels_list)
            
            # Đọc reviews
            reviews_df = pd.read_csv("reviews.csv", encoding='utf-8-sig')
            reviews_list = []
            for _, review in reviews_df.tail(5).iterrows():
                reviews_list.append(f"{review['hotel_name']}: {review['user']} - ⭐{review['rating']} - {review['comment'][:100]}")
            reviews_info = "\n".join(reviews_list)
            
            # Đọc events
            events_df = pd.read_csv("events.csv", encoding='utf-8-sig')
            events_list = []
            for _, event in events_df.iterrows():
                events_list.append(f"{event['event_name']} tại {event['city']} ({event['start_date']} đến {event['end_date']}) - Mùa: {event.get('season', 'Không xác định')}")
            events_info = "\n".join(events_list)
            
        except Exception as e:
            print(f"Lỗi đọc CSV: {e}")
            hotels_info = "Không thể đọc dữ liệu khách sạn"
            reviews_info = "Không thể đọc đánh giá"
            events_info = "Không thể đọc sự kiện"

        # 3. Xây dựng prompt TOÀN DIỆN và LINH HOẠT
        system_prompt = f"""
Bạn là một trợ lý du lịch TOÀN DIỆN có thể xử lý MỌI loại câu hỏi về khách sạn, du lịch, sự kiện, và cả tâm trạng.

DỮ LIỆU HIỆN CÓ:

🏨 TOÀN BỘ KHÁCH SẠN (Tên & Thành phố):
{hotels_info}

📝 ĐÁNH GIÁ GẦN ĐÂY:
{reviews_info}

🎪 SỰ KIỆN & MÙA:
{events_info}

HƯỚNG DẪN XỬ LÝ CÁC LOẠI CÂU HỎI:

1. CÂU HỎI VỀ TÂM TRẠNG (buồn, vui, stress, v.v.):
   - ĐẦU TIÊN: Thấu hiểu và đồng cảm
   - PHÂN TÍCH: Nhu cầu thực sự ẩn sau cảm xúc
   - ĐỀ XUẤT: Khách sạn phù hợp với tâm trạng
   - VÍ DỤ: Buồn → spa, yên tĩnh; Vui → bar, hồ bơi

2. CÂU HỎI VỀ MÙA & SỰ KIỆN:
   - KIỂM TRA: Sự kiện trong events.csv
   - TƯ VẤN: Mùa nào đẹp, sự kiện gì diễn ra
   - KẾT HỢP: Đề xuất khách sạn gần sự kiện

3. CÂU HỎI VỀ KHÁCH SẠN CỤ THỂ:
   - TÌM KIẾM: Thông tin khách sạn trong danh sách
   - MÔ TẢ: Đặc điểm, tiện ích nếu có trong dữ liệu
   - SO SÁNH: Với các khách sạn khác cùng khu vực

4. CÂU HỎI CHUNG VỀ DU LỊCH:
   - SỬ DỤNG: Kiến thức du lịch tổng hợp
   - KẾT HỢP: Với dữ liệu khách sạn hiện có
   - ĐỀ XUẤT: Dựa trên ngân sách, sở thích

QUY TẮC TRẢ LỜI:
- LUÔN bắt đầu bằng sự thấu hiểu với người dùng
- PHÂN TÍCH loại câu hỏi trước khi trả lời
- SỬ DỤNG dữ liệu từ CSV khi có thông tin phù hợp
- LIỆT KÊ khách sạn RÕ RÀNG khi cần đề xuất
- Format đơn giản: • Tên khách sạn (Thành phố)
- KHÔNG bịa thông tin không có trong dữ liệu
- Nếu không có dữ liệu, dùng kiến thức chung và nói rõ

VÍ DỤ XỬ LÝ CÁC TÌNH HUỐNG:

"Tôi vừa chia tay ny nên hơi buồn":
→ "Tôi hiểu bạn đang trải qua khoảng thời gian khó khăn. Những khách sạn có không gian yên tĩnh, view đẹp và dịch vụ spa sẽ giúp bạn thư giãn:
• Serenity Resort (Đà Nẵng)
• Peaceful Haven (Nha Trang)
• Tranquil Bay (Phú Quốc)"

"Sunrise Nha Trang thì tôi nên đi vào những mùa nào, có sự kiện gì gần đó không":
→ "Sunrise Nha Trang là một lựa chọn tuyệt vời! Về mùa du lịch:
- Tháng 2-8: Mùa khô, nắng đẹp, biển trong
- Tháng 9-1: Có mưa nhưng ít khách du lịch

Sự kiện gần đó:
• Carnival Biển Nha Trang (tháng 6)
• Lễ hội Ẩm thực Biển (tháng 8)

Bạn có muốn tôi tìm thêm khách sạn tương tự không?"

Hãy PHÂN TÍCH kỹ câu hỏi và đưa ra câu trả lời PHÙ HỢP NHẤT!
"""

        # 4. Gọi Gemini với retry logic
        max_retries = 2
        for attempt in range(max_retries):
            try:
                response = model.generate_content(
                    system_prompt + "\n\nCâu hỏi của người dùng: " + user_query,
                    generation_config=genai.GenerationConfig(
                        temperature=0.8,
                        max_output_tokens=1500
                    )
                )
                ai_response = response.text
                
                # Clean up response
                cleaned_response = ai_response.replace('**', '').replace('*', '')
                return jsonify({"response": cleaned_response})
                
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
        fallback_responses = [
            "Hiện tại hệ thống đang gặp sự cố kỹ thuật. Tôi vẫn muốn lắng nghe và hỗ trợ bạn. Hãy thử lại sau ít phút nhé!",
            "Xin lỗi, tôi đang gặp vấn đề kết nối. Dù vậy, tôi luôn sẵn sàng hỗ trợ bạn. Hãy thử lại sau hoặc dùng tính năng tìm kiếm thông thường.",
        ]
        import random
        return jsonify({"response": random.choice(fallback_responses)})

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








