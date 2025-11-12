import pandas as pd

def calculate_scores_and_explain(df, all_prefs):
    print(f"[AI] Bắt đầu tính điểm. Sở thích: {all_prefs}")
    
    # Một danh sách để lưu lại các lý do giải thích
    explanation_log = ["Bắt đầu quá trình xếp hạng:"]
    
    # Tạo bản sao để tính toán
    df_scored = df.copy()
    
    # DEBUG: Kiểm tra kiểu dữ liệu
    print(f"🔍 Số lượng khách sạn: {len(df_scored)}")
    print(f"🔍 Columns: {list(df_scored.columns)}")
    
    # LỌC CỨNG (Hard Filter) ---
    min_stars = all_prefs.get('min_stars', 0)
    if min_stars > 0:
        df_scored = df_scored[df_scored['stars'] >= min_stars].copy()
        explanation_log.append(f"Loại bỏ các khách sạn dưới {min_stars} sao.")
    
    if df_scored.empty:
        return df_scored, "Không tìm thấy khách sạn nào sau khi lọc theo số sao."

    # ĐẢM BẢO KIỂU DỮ LIỆU SỐ
    try:
        # Convert các cột số
        numeric_columns = ['price', 'stars', 'rating']
        for col in numeric_columns:
            if col in df_scored.columns:
                # Chuyển đổi sang số, nếu lỗi thì thành 0
                df_scored[col] = pd.to_numeric(df_scored[col], errors='coerce').fillna(0)
                print(f"✅ Converted {col} to numeric")
        
        # Convert các cột boolean từ string sang boolean
        boolean_columns = ['pool', 'sea', 'view', 'spa', 'buffet', 'gym']
        for col in boolean_columns:
            if col in df_scored.columns:
                # Chuyển đổi 'True'/'False' string sang boolean
                df_scored[col] = df_scored[col].apply(
                    lambda x: str(x).strip().lower() in ['true', '1', 'yes', 'có', '1.0', 'true.0', '1']
                )
                print(f"✅ Converted {col} to boolean. Sample: {df_scored[col].iloc[0] if len(df_scored) > 0 else 'N/A'}")
        
        # Khởi tạo điểm số
        df_scored['recommend_score'] = 0
                
    except Exception as e:
        print(f"⚠️ Lỗi convert dữ liệu: {e}")
        # Khởi tạo điểm số mặc định nếu có lỗi
        df_scored['recommend_score'] = 0

    # TÍNH ĐIỂM (Scoring Logic) - ƯU TIÊN HEALING ---
    
    # ĐIỂM CƠ BẢN: Rating quan trọng nhất
    df_scored['recommend_score'] += df_scored['rating'] * 5
    explanation_log.append("Điểm cơ bản dựa trên rating.")

    # 1. TÍNH ĐIỂM TIỆN ÍCH - ƯU TIÊN HEALING
    healing_features = {
        'pool': 15,      # Hồ bơi - quan trọng nhất
        'sea': 12,       # View biển - rất quan trọng  
        'view': 10,      # View đẹp - quan trọng
        'spa': 8,        # Spa - quan trọng
        'buffet': 6,     # Buffet - khá quan trọng
        'gym': 4         # Gym - ít quan trọng hơn
    }

    # XỬ LÝ TEXT TÌM KIẾM - HỖ TRỢ CẢ TIẾNG VIỆT
    user_text = all_prefs.get('text_query', '').lower()

    # MAPPING TỪ KHÓA TIẾNG VIỆT SANG TIẾNG ANH
    vietnamese_to_english = {
        # Tiện ích
        'hồ bơi': 'pool', 'bể bơi': 'pool', 'bơi lội': 'pool',
        'view biển': 'sea', 'biển': 'sea', 'gần biển': 'sea', 'biển cả': 'sea',
        'spa': 'spa', 'massage': 'spa', 'xông hơi': 'spa',
        'buffet': 'buffet', 'ăn sáng': 'buffet', 'bữa sáng': 'buffet',
        'gym': 'gym', 'thể hình': 'gym', 'tập thể dục': 'gym', 'phòng gym': 'gym',
        'view': 'view', 'cảnh đẹp': 'view', 'view thành phố': 'view',
        'giá rẻ': 'price_low', 'rẻ': 'price_low', 'giá thấp': 'price_low', 'giá tốt': 'price_low',
        'đánh giá tốt': 'high_rating', 'nhiều sao': 'high_rating', 'rating cao': 'high_rating'
    }

    # CHUYỂN ĐỔI TỪ KHÓA TIẾNG VIỆT SANG TIẾNG ANH
    translated_text = user_text
    for viet_word, eng_word in vietnamese_to_english.items():
        if viet_word in user_text:
            translated_text += " " + eng_word

    # Xử lý các tính năng bằng cả tiếng Việt và Anh
    for feature, base_score in healing_features.items():
        # Tìm từ khóa tiếng Việt tương ứng
        viet_keywords = [viet for viet, eng in vietnamese_to_english.items() if eng == feature]
        
        # Kiểm tra cả tiếng Việt và tiếng Anh
        has_feature_request = (all_prefs.get(feature, False) or 
                              any(keyword in user_text for keyword in viet_keywords) or
                              feature in translated_text)
        
        if has_feature_request:
            print(f"🎯 Phát hiện yêu cầu {feature}, thêm điểm cho khách sạn có tính năng này")
            df_scored['recommend_score'] += df_scored[feature].apply(
                lambda has_feature: base_score if has_feature else 0
            )
            explanation_log.append(f"Phát hiện yêu cầu {feature}, ưu tiên khách sạn có tính năng này.")

    # 2. BONUS CHO KHÁCH SẠN CÓ NHIỀU TIỆN ÍCH HEALING
    healing_count = 0
    for feat in healing_features.keys():
        if feat in df_scored.columns:
            healing_count += df_scored[feat].sum()
    
    df_scored['recommend_score'] += healing_count * 2
    explanation_log.append("Thêm điểm cho khách sạn có nhiều tiện ích healing.")

    # 3. ĐIỂM SỐ SAO - RẤT QUAN TRỌNG
    df_scored['recommend_score'] += df_scored['stars'] * 8
    explanation_log.append("Ưu tiên khách sạn nhiều sao.")

    # Xử lý "giá rẻ" - cả tiếng Việt và Anh
    if 'giá rẻ' in user_text or 'rẻ' in user_text or 'giá thấp' in user_text or 'cheap' in translated_text:
        max_price = df_scored['price'].max()
        if max_price > 0:
            df_scored['recommend_score'] += ((max_price - df_scored['price']) / max_price) * 20
        explanation_log.append("Ưu tiên khách sạn giá rẻ.")
    
    # Xử lý "nhiều đánh giá tích cực"
    if 'nhiều đánh giá tích cực' in user_text or 'đánh giá tốt' in user_text:
        df_scored['recommend_score'] += df_scored['rating'] * 3
        explanation_log.append("Ưu tiên khách sạn có đánh giá cao.")

    # 4. ĐẢM BẢO ĐIỂM KHÔNG ÂM VÀ LÀM TRÒN
    df_scored['recommend_score'] = df_scored['recommend_score'].round(2)
    df_scored['recommend_score'] = df_scored['recommend_score'].clip(lower=0)
    
    # DEBUG: Hiển thị điểm số
    print(f"🎯 Điểm số min: {df_scored['recommend_score'].min()}, max: {df_scored['recommend_score'].max()}")
    print(f"🎯 Top 3 khách sạn:")
    for i, (_, hotel) in enumerate(df_scored.nlargest(3, 'recommend_score').iterrows(), 1):
        print(f"   {i}. {hotel['name']} - Điểm: {hotel['recommend_score']}")
    
    # SẮP XẾP (Sorting) ---
    final_results_sorted = df_scored.sort_values(by="recommend_score", ascending=False)
    explanation_log.append("Hoàn tất! Đã sắp xếp kết quả theo tiêu chí healing và số sao.")

    # TRẢ VỀ KẾT QUẢ ---
    final_explanation = " | ".join(explanation_log)

    num_results = min(5, len(final_results_sorted))
    print(f"[AI] Trả về {num_results} khách sạn")
    
    return final_results_sorted, final_explanation
