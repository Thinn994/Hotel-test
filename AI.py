import math
import pandas as pd
from datetime import datetime

def haversine(lat1, lon1, lat2, lon2):
    """Tính khoảng cách km giữa 2 tọa độ"""
    R = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

def month_to_season(month):
    if month in (3,4,5): return 'spring'
    if month in (6,7,8): return 'summer'
    if month in (9,10,11): return 'autumn'
    return 'winter'


weather_rules = {
    'sunny': lambda amenities: 1.0 if ('pool' in amenities or 'sea' in amenities) else 0.3,
    'rain':  lambda amenities: 1.0 if ('buffet' in amenities or 'view' in amenities) else 0.3,
    'cloudy': lambda amenities: 0.6,
    'default': lambda amenities: 0.5
}

season_rules = {
    'spring': lambda amenities, tags: 1.0 if 'view' in amenities else 0.5,
    'summer': lambda amenities, tags: 1.0 if 'pool' in amenities or 'sea' in amenities else 0.5,
    'autumn': lambda amenities, tags: 0.7,
    'winter': lambda amenities, tags: 1.0 if 'buffet' in amenities else 0.5
}


def score_event(hotel_row, events_df, reference_date):
    min_days = float('inf')
    nearest_event = None
    
  
    city_events = events_df[events_df['city'] == hotel_row['city']]
    if city_events.empty:
        return 0.1 

    for _, ev in city_events.iterrows():
        event_date = ev['start_date']
        delta_days = abs((event_date - reference_date).days)
       
        if 0 <= delta_days <= 30 and delta_days < min_days:
            nearest_event = ev
            min_days = delta_days
    
    for _, ev in city_events.iterrows():
        event_date = ev['start_date']
        delta_days = abs((event_date - reference_date).days)
        if 0 <= delta_days <= 30 and delta_days < min_days:
            nearest_event = ev
            min_days = delta_days

def score_weather(hotel_row, condition):
    amenities = []
    if hotel_row['pool']: amenities.append('pool')
    if hotel_row['sea']: amenities.append('sea')
    if hotel_row['buffet']: amenities.append('buffet')
    if hotel_row['view']: amenities.append('view')
    
    rule = weather_rules.get(condition, weather_rules['default'])
    return rule(amenities)

def score_season(hotel_row, season_name):
    amenities = []
    if hotel_row['pool']: amenities.append('pool')
    if hotel_row['sea']: amenities.append('sea')
    if hotel_row['buffet']: amenities.append('buffet')
    if hotel_row['view']: amenities.append('view')
    
  
    rule = season_rules.get(season_name, lambda a, t: 0.5)
    return rule(amenities, None)


def get_hotel_recommendations(input_date_str='2025-11-20', input_weather_condition='sunny'):
    """
    Hàm chính để tính toán và trả về điểm số gợi ý.
    Trả về một DataFrame với cột 'name' và 'recommend_score'.
    """
    try:
        hotels_df = pd.read_csv("hotels.csv", encoding='utf-8-sig')
        events_df = pd.read_csv("events.csv", encoding='utf-8-sig')
        
        
        events_df['start_date'] = pd.to_datetime(events_df['start_date'])
        
       
        try:
            reference_date = datetime.strptime(input_date_str, '%Y-%m-%d')
        except ValueError:
            reference_date = datetime.now()

        season = month_to_season(reference_date.month)
        current_weather = {'condition': input_weather_condition}

       
        results = []
        for _, h in hotels_df.iterrows():
            s_event = score_event(h, events_df, reference_date)
            s_weather = score_weather(h, current_weather['condition'])
            s_season = score_season(h, season)
            
           
            total = 0.4 * s_event + 0.3 * s_weather + 0.3 * s_season
            
            results.append({
                'name': h['name'],
                'recommend_score': round(total, 2) 
            })
        
      
        result_df = pd.DataFrame(results)
       
        return result_df.sort_values(by='recommend_score', ascending=False)

    except FileNotFoundError:
        print("Lỗi: Không tìm thấy file hotels.csv hoặc events.csv.")
        return pd.DataFrame(columns=['name', 'recommend_score'])
    except Exception as e:
        print(f"Lỗi trong AI.py: {e}")
        return pd.DataFrame(columns=['name', 'recommend_score'])


if __name__ == '__main__':
    print("--- Chạy test AI.py ---")
    recommendations = get_hotel_recommendations(input_date_str='2025-07-10', input_weather_condition='sunny')
    print(recommendations.head())
    print("------------------------")
