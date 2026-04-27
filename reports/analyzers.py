import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from django.db.models import Avg, Max, Min, Count
from solar_data.models import DailyClimateData, Location  # Fixed: was core.models
import json
import matplotlib
matplotlib.use('Agg')  # للاستخدام بدون واجهة رسومية
import matplotlib.pyplot as plt
import io
import base64


class SolarEnergyAnalyzer:
    """محلل الطاقة الشمسية المتقدم"""

    def __init__(self):
        self.results = {}

    def analyze_location(self, location_id):
        """تحليل متقدم لموقع"""
        location = Location.objects.get(id=location_id)
        region = location.governorate.name if location.governorate else 'Unknown'

        # جمع البيانات — Fixed: was ClimateData with sampling_point__city
        data = DailyClimateData.objects.filter(
            location=location
        ).values('date', 'allsky_sfc_sw_dwn', 't2m', 'dust_risk_score')

        df = pd.DataFrame(list(data))

        if df.empty:
            return None

        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)

        # التحليل الشهري — Fixed: field names from solar_radiation/temperature_avg to allsky_sfc_sw_dwn/t2m
        monthly_stats = df.resample('ME').agg({
            'allsky_sfc_sw_dwn': ['mean', 'min', 'max', 'std'],
            't2m': 'mean',
            'dust_risk_score': 'mean'
        })

        # التحليل الموسمي
        df['season'] = df.index.month.map(self._get_season)
        seasonal_stats = df.groupby('season').agg({
            'allsky_sfc_sw_dwn': ['mean', 'std'],
            't2m': 'mean'
        })

        trend_analysis = self._analyze_trends(df)
        dust_impact = self._calculate_dust_impact(df)

        report = {
            'location': {
                'name': location.name,
                'region': region,
                'governorate': location.governorate.name if location.governorate else None,
            },
            'monthly_stats': monthly_stats.to_dict(),
            'seasonal_stats': seasonal_stats.to_dict(),
            'trend_analysis': trend_analysis,
            'dust_impact': dust_impact,
            'recommendations': self._generate_recommendations(df)
        }

        return report

    # Keep old name as alias for backwards-compatibility
    def analyze_city(self, city_id):
        return self.analyze_location(city_id)

    def _get_season(self, month):
        """تحديد الموسم"""
        if month in [12, 1, 2]:
            return 'شتاء'
        elif month in [3, 4, 5]:
            return 'ربيع'
        elif month in [6, 7, 8]:
            return 'صيف'
        else:
            return 'خريف'

    def _analyze_trends(self, df):
        """تحليل الاتجاهات الزمنية"""
        df = df.copy()
        df['year'] = df.index.year
        df['month'] = df.index.month

        annual_trend = df.groupby('year')['allsky_sfc_sw_dwn'].mean().to_dict()
        monthly_pattern = df.groupby('month')['allsky_sfc_sw_dwn'].mean().to_dict()

        return {
            'annual_trend': annual_trend,
            'monthly_pattern': monthly_pattern,
            'best_month': max(monthly_pattern, key=monthly_pattern.get) if monthly_pattern else None,
            'worst_month': min(monthly_pattern, key=monthly_pattern.get) if monthly_pattern else None
        }

    def _calculate_dust_impact(self, df):
        """حساب تأثير الغبار"""
        if 'dust_risk_score' not in df.columns or df['dust_risk_score'].isna().all():
            return {'estimated_impact': 5.0}

        dust_col = df['dust_risk_score'].dropna()
        correlation = df['allsky_sfc_sw_dwn'].corr(dust_col)
        avg_dust = dust_col.mean()

        impact_percentage = (1 - avg_dust) * 100

        return {
            'avg_dust_index': round(avg_dust, 3),
            'correlation_with_radiation': round(correlation, 3) if not np.isnan(correlation) else 0,
            'estimated_impact_percentage': round(impact_percentage, 2),
            'cleaning_recommendation': self._get_cleaning_recommendation(avg_dust)
        }

    def _get_cleaning_recommendation(self, dust_index):
        """توصيات التنظيف"""
        if dust_index > 0.6:
            return {'frequency': 'كل أسبوعين', 'priority': 'عالية'}
        elif dust_index > 0.4:
            return {'frequency': 'كل 3 أسابيع', 'priority': 'متوسطة'}
        else:
            return {'frequency': 'شهرياً', 'priority': 'منخفضة'}

    def _generate_recommendations(self, df):
        """توليد توصيات مخصصة"""
        avg_radiation = df['allsky_sfc_sw_dwn'].mean()
        recommendations = []

        if avg_radiation >= 6.0:
            recommendations.append({
                'type': 'نظام_كبير',
                'message': 'إمكانات ممتازة - يمكن تركيب نظام كبير (10+ كيلوواط)',
                'priority': 'عالية'
            })
        elif avg_radiation >= 5.0:
            recommendations.append({
                'type': 'نظام_متوسط',
                'message': 'إمكانات جيدة - نظام متوسط الحجم (5-10 كيلوواط) مناسب',
                'priority': 'متوسطة'
            })

        avg_temp = df['t2m'].mean()
        if avg_temp > 35:
            recommendations.append({
                'type': 'تبريد_الألواح',
                'message': 'درجات حرارة عالية - مراعاة تبريد الألواح لزيادة الكفاءة',
                'priority': 'متوسطة'
            })

        return recommendations

    def generate_visualization(self, location_id):
        """توليد رسوميات بيانية"""
        location = Location.objects.get(id=location_id)

        # Fixed: was ClimateData with sampling_point__city
        data = DailyClimateData.objects.filter(
            location=location
        ).values('date', 'allsky_sfc_sw_dwn', 't2m')

        df = pd.DataFrame(list(data))
        if df.empty:
            return None

        df['date'] = pd.to_datetime(df['date'])

        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))

        ax1.plot(df['date'], df['allsky_sfc_sw_dwn'], 'b-', alpha=0.7)
        ax1.set_title(f'Solar Radiation — {location.name}', fontsize=14)
        ax1.set_ylabel('kWh/m²/day')
        ax1.grid(True, alpha=0.3)

        ax2.plot(df['date'], df['t2m'], 'r-', alpha=0.7)
        ax2.set_title(f'Avg Temperature — {location.name}', fontsize=14)
        ax2.set_ylabel('°C')
        ax2.set_xlabel('Date')
        ax2.grid(True, alpha=0.3)

        plt.tight_layout()

        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=100)
        buf.seek(0)

        img_str = base64.b64encode(buf.read()).decode('utf-8')
        plt.close()

        return img_str
