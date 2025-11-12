import pandas as pd

def calculate_scores_and_explain(df, all_prefs):
    print(f"[AI] Bắt đầu tính điểm. Sở thích: {all_prefs}")
    
    # Một danh sách để lưu lại các lý do giải thích
    explanation_log = ["Bắt đầu quá trình xếp hạng:"]
    
    # Tạo bản sao để tính toán
    df_scored = df.copy()
    
    # LỌC CỨNG (Hard Filter) ---
    min_stars = all_prefs.get('min_stars', 0)
    if min_stars > 0:
        df_scored = df_scored[df_scored['stars'] >= min_stars].copy()
        explanation_log.append(f"Loại bỏ các khách sạn dưới {min_stars} sao.")
    
    if df_scored.empty:
        return df_scored, "Không tìm thấy khách sạn nào sau khi lọc theo số sao."

    # TÍNH ĐIỂM (Scoring Logic) - ƯU TIÊN HEALING ---
    
    # ĐIỂM CƠ BẢN: Rating quan trọng nhất
    df_scored['recommend_score'] = df_scored['rating'] * 5  # Tăng hệ số rating
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

    for feature, base_score in healing_features.items():
        if all_prefs.get(feature, False):
            # Khách sạn có tính năng được yêu cầu
            df_scored['recommend_score'] += df_scored[feature].apply(
                lambda has_feature: base_score if has_feature else 0
            )
            explanation_log.append(f"Ưu tiên khách sạn có {feature}.")
            
            # THÊM ĐIỂM BONUS NẾU CÓ NHIỀU TIỆN ÍCH HEALING
            if has_feature:
                other_healing_features = [f for f in healing_features.keys() if f != feature]
                bonus_count = sum(df_scored[other_feat] for other_feat in other_healing_features)
                bonus_score = bonus_count * 3
                df_scored['recommend_score'] += bonus_score

    # 2. BONUS CHO KHÁCH SẠN CÓ NHIỀU TIỆN ÍCH HEALING
    healing_count = sum(df_scored[feat] for feat in healing_features.keys())
    df_scored['recommend_score'] += healing_count * 2
    explanation_log.append("Thêm điểm cho khách sạn có nhiều tiện ích healing.")

    # 3. ĐIỂM SỐ SAO - RẤT QUAN TRỌNG
    df_scored['recommend_score'] += df_scored['stars'] * 8
    explanation_log.append("Ưu tiên khách sạn nhiều sao.")

    # 4. XỬ LÝ TEXT TÌM KIẾM - HỖ TRỢ CẢ TIẾNG VIỆT
    user_text = all_prefs.get('text', '').lower()
    user_query = all_prefs.get('text_query', '').lower()
    combined_text = user_text + " " + user_query

    # MAPPING TỪ KHÓA TIẾNG VIỆT SANG TIẾNG ANH
    vietnamese_to_english = {
        # Tiện ích
        'hồ bơi': 'pool', 'bể bơi': 'pool', 'bơi lội': 'pool',
        'view biển': 'sea', 'biển': 'sea', 'gần biển': 'sea',
        'spa': 'spa', 'massage': 'spa', 
        'buffet': 'buffet', 'ăn sáng': 'buffet',
        'gym': 'gym', 'thể hình': 'gym', 'tập thể dục': 'gym',
        'view': 'view', 'cảnh đẹp': 'view',
        
        # Từ khóa healing
        'healing': 'healing', 'thư giãn': 'thư giãn', 'nghỉ dưỡng': 'nghỉ dưỡng',
        'yên tĩnh': 'yên tĩnh', 'thanh bình': 'yên tĩnh',
        
        # Giá cả
        'giá rẻ': 'giá rẻ', 'rẻ': 'giá rẻ', 'giá thấp': 'giá rẻ',
        'đánh giá tốt': 'đánh giá tốt', 'nhiều sao': 'nhiều sao'
    }

    # CHUYỂN ĐỔI TỪ KHÓA TIẾNG VIỆT SANG TIẾNG ANH
    translated_text = combined_text
    for viet_word, eng_word in vietnamese_to_english.items():
        if viet_word in combined_text:
            translated_text += " " + eng_word

    # Xử lý "giá rẻ" - cả tiếng Việt và Anh
    if 'giá rẻ' in combined_text or 'rẻ' in combined_text or 'giá thấp' in combined_text or 'cheap' in translated_text:
        max_price = df_scored['price'].max()
        if max_price > 0:
            df_scored['recommend_score'] += ((max_price - df_scored['price']) / max_price) * 20
        explanation_log.append("Ưu tiên khách sạn giá rẻ.")
    
    # Xử lý "nhiều đánh giá tích cực"
    if 'nhiều đánh giá tích cực' in combined_text or 'đánh giá tốt' in combined_text:
        df_scored['recommend_score'] += df_scored['rating'] * 3
        explanation_log.append("Ưu tiên khách sạn có đánh giá cao.")

    # Xử lý các tính năng bằng cả tiếng Việt và Anh
    # KIỂM TRA CẢ TỪ KHÓA TIẾNG VIỆT
    for feature, base_score in healing_features.items():
        # Tìm từ khóa tiếng Việt tương ứng
        viet_keywords = [viet for viet, eng in vietnamese_to_english.items() if eng == feature]
        
        # Kiểm tra cả tiếng Việt và tiếng Anh
        has_feature_request = (all_prefs.get(feature, False) or 
                              any(keyword in combined_text for keyword in viet_keywords) or
                              feature in translated_text)
        
        if has_feature_request:
            df_scored['recommend_score'] += df_scored[feature].apply(
                lambda has_feature: base_score if has_feature else 0
            )
            explanation_log.append(f"Ưu tiên khách sạn có {feature}.")
            
            # Bonus cho nhiều tiện ích
            if has_feature:
                other_healing_features = [f for f in healing_features.keys() if f != feature]
                bonus_count = sum(df_scored[other_feat] for other_feat in other_healing_features)
                bonus_score = bonus_count * 3
                df_scored['recommend_score'] += bonus_score

    # Xử lý từ khóa healing bằng cả tiếng Việt
    healing_keywords_mapping = {
        'healing': ['pool', 'sea', 'spa', 'view'],
        'thư giãn': ['spa', 'pool', 'sea'],
        'nghỉ dưỡng': ['spa', 'pool', 'sea', 'view'],
        'yên tĩnh': ['spa', 'view']
    }

    for keyword, features in healing_keywords_mapping.items():
        # Kiểm tra cả tiếng Việt và từ mapped
        if keyword in translated_text:
            for feature in features:
                df_scored['recommend_score'] += df_scored[feature].apply(
                    lambda has_feature: 8 if has_feature else 0
                )
            explanation_log.append(f"Phát hiện từ khóa healing, ưu tiên tiện ích phù hợp.")

    # 5. ĐẢM BẢO ĐIỂM KHÔNG ÂM VÀ LÀM TRÒN
    df_scored['recommend_score'] = df_scored['recommend_score'].round(2)
    df_scored['recommend_score'] = df_scored['recommend_score'].clip(lower=0)
    
    # SẮP XẾP (Sorting) ---
    final_results_sorted = df_scored.sort_values(by="recommend_score", ascending=False)
    explanation_log.append("Hoàn tất! Đã sắp xếp kết quả theo tiêu chí healing và số sao.")

    # TRẢ VỀ KẾT QUẢ ---
    final_explanation = " | ".join(explanation_log)

    num_results = min(5, len(final_results_sorted))
    print(f"[AI] Trả về {num_results} khách sạn")
    
    return final_results_sorted, final_explanation
