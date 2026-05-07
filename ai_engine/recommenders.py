import numpy as np
from django.db.models import Avg
from solar_data.models import DailyClimateData, Location  # Fixed: was core.models
import json


class SolarDesignRecommender:
    """مُوصي تصميم الأنظمة الشمسية"""

    def __init__(self):
        # أسعار معدلات مصرية (بالجنيه المصري)
        self.equipment_prices = {
            'panel_330w': 1800,
            'panel_400w': 2200,
            'inverter_3kw': 15000,
            'inverter_5kw': 25000,
            'inverter_10kw': 45000,
            'battery_5kwh': 20000,
            'mounting_system': 500,
            'installation': 10000
        }

        # عوامل مصرية خاصة
        self.egyptian_factors = {
            'dust_impact': 0.95,
            'temperature_impact': 0.98,
            'maintenance_cost': 0.02,
            'inflation_rate': 0.15,
            'electricity_price': 1.20
        }

    def recommend_design(self, location_id, monthly_consumption, budget, roof_area):
        """توصية بتصميم نظام شمسي"""
        location = Location.objects.get(id=location_id)

        solar_potential = self._calculate_solar_potential(location_id)

        daily_consumption = monthly_consumption / 30

        region = location.governorate.name if location.governorate else 'Unknown'

        system_size_kw = self._calculate_system_size(
            daily_consumption,
            solar_potential,
            region
        )

        design_options = self._generate_design_options(
            system_size_kw,
            budget,
            roof_area,
            region
        )

        for option in design_options:
            option['economic_analysis'] = self._economic_analysis(
                option,
                monthly_consumption,
                region
            )

        design_options.sort(key=lambda x: x['economic_analysis']['roi_score'], reverse=True)

        return {
            'location': location.name,
            'solar_potential_kwh_m2_day': solar_potential,
            'recommended_system_size_kw': system_size_kw,
            'design_options': design_options[:3],
            'factors_considered': {
                'regional_dust': self._get_regional_dust_factor(region),
                'temperature_impact': self._get_temperature_impact(region),
                'egyptian_market_prices': True
            }
        }

    def _calculate_solar_potential(self, location_id):
        """حساب الإمكانات الشمسية للموقع"""
        avg_radiation = DailyClimateData.objects.filter(
            location_id=location_id
        ).aggregate(Avg('allsky_sfc_sw_dwn'))['allsky_sfc_sw_dwn__avg']

        return round(avg_radiation or 5.5, 2)

    def _calculate_system_size(self, daily_consumption, solar_potential, region):
        """حساب حجم النظام المطلوب"""
        regional_factors = {
            'القاهرة': 0.95,
            'الإسكندرية': 0.97,
            'الجيزة': 0.95,
            'أسوان': 1.05,
            'البحر الأحمر': 1.03,
        }

        factor = regional_factors.get(region, 1.0)
        system_efficiency = 0.75
        system_size = daily_consumption / (solar_potential * system_efficiency * factor)

        return round(max(1.0, system_size), 2)

    def _generate_design_options(self, system_size_kw, budget, roof_area, region):
        """توليد خيارات تصميمية"""
        options = []

        basic_option = self._create_basic_design(system_size_kw, budget, roof_area, region)
        if basic_option:
            options.append(basic_option)

        balanced_option = self._create_balanced_design(system_size_kw, budget, roof_area, region)
        if balanced_option:
            options.append(balanced_option)

        premium_option = self._create_premium_design(system_size_kw, budget, roof_area, region)
        if premium_option:
            options.append(premium_option)

        return options

    def _create_basic_design(self, system_size_kw, budget, roof_area, region):
        """تصميم نظام أساسي — ألواح 330 واط"""
        panel_type = 'panel_330w'
        panel_watts = 330
        panels_needed = int((system_size_kw * 1000) / panel_watts)

        panel_area = 1.6
        required_area = panels_needed * panel_area

        if required_area > roof_area:
            return None

        total_cost = self._calculate_total_cost(panels_needed, panel_type, system_size_kw)

        if total_cost > budget * 1.2:
            return None

        return {
            'name': 'النظام الأساسي',
            'description': 'أقل تكلفة، مناسبة للميزانيات المحدودة',
            'panel_type': 'ألواح 330 واط',
            'panel_count': panels_needed,
            'inverter_size': f"{min(10, max(3, int(system_size_kw)))} كيلوواط",
            'battery': 'غير مدرجة',
            'estimated_cost_egp': total_cost,
            'estimated_yearly_energy_kwh': self._estimate_yearly_energy(panels_needed, panel_watts, region),
            'space_required_m2': required_area,
            'suitability': 'منازل صغيرة، محلات تجارية صغيرة'
        }

    def _create_balanced_design(self, system_size_kw, budget, roof_area, region):
        """تصميم نظام متوازن — ألواح 400 واط"""
        panel_type = 'panel_400w'
        panel_watts = 400
        panels_needed = int((system_size_kw * 1000) / panel_watts)

        panel_area = 1.7
        required_area = panels_needed * panel_area

        if required_area > roof_area:
            return None

        total_cost = self._calculate_total_cost(panels_needed, panel_type, system_size_kw)

        if total_cost > budget * 1.4:
            return None

        return {
            'name': 'النظام المتوازن',
            'description': 'أفضل قيمة، توازن بين التكلفة والكفاءة',
            'panel_type': 'ألواح 400 واط',
            'panel_count': panels_needed,
            'inverter_size': f"{min(10, max(3, int(system_size_kw)))} كيلوواط",
            'battery': 'غير مدرجة',
            'estimated_cost_egp': total_cost,
            'estimated_yearly_energy_kwh': self._estimate_yearly_energy(panels_needed, panel_watts, region),
            'space_required_m2': required_area,
            'suitability': 'منازل متوسطة، مكاتب صغيرة'
        }

    def _create_premium_design(self, system_size_kw, budget, roof_area, region):
        """تصميم نظام متقدم — ألواح 400 واط + بطارية"""
        panel_type = 'panel_400w'
        panel_watts = 400
        panels_needed = int((system_size_kw * 1000) / panel_watts) + 2  # extra panels for battery charging

        panel_area = 1.7
        required_area = panels_needed * panel_area

        if required_area > roof_area:
            return None

        total_cost = self._calculate_total_cost(panels_needed, panel_type, system_size_kw)
        total_cost += self.equipment_prices['battery_5kwh']  # add battery
        total_cost = int(total_cost * 1.14)  # VAT on battery

        if total_cost > budget * 1.6:
            return None

        return {
            'name': 'النظام المتقدم',
            'description': 'أعلى كفاءة مع تخزين، مناسب للمناطق ذات الانقطاع المتكرر',
            'panel_type': 'ألواح 400 واط + بطارية 5 كيلوواط ساعة',
            'panel_count': panels_needed,
            'inverter_size': f"{min(10, max(5, int(system_size_kw)))} كيلوواط",
            'battery': 'بطارية 5 كيلوواط ساعة',
            'estimated_cost_egp': total_cost,
            'estimated_yearly_energy_kwh': self._estimate_yearly_energy(panels_needed, panel_watts, region),
            'space_required_m2': required_area,
            'suitability': 'منازل كبيرة، مشاريع تجارية متوسطة'
        }

    def _calculate_total_cost(self, panel_count, panel_type, system_size_kw):
        """حساب التكلفة الإجمالية"""
        panel_cost = panel_count * self.equipment_prices[panel_type]

        if system_size_kw <= 3:
            inverter_cost = self.equipment_prices['inverter_3kw']
        elif system_size_kw <= 5:
            inverter_cost = self.equipment_prices['inverter_5kw']
        else:
            inverter_cost = self.equipment_prices['inverter_10kw']

        mounting_cost = panel_count * self.equipment_prices['mounting_system']
        installation_cost = self.equipment_prices['installation']

        total = panel_cost + inverter_cost + mounting_cost + installation_cost
        total *= 1.14  # VAT 14%

        return int(total)

    def _estimate_yearly_energy(self, panel_count, panel_watts, region):
        """تقدير الطاقة السنوية"""
        sun_hours = {
            'القاهرة': 9.5,
            'الإسكندرية': 9.0,
            'الجيزة': 9.5,
            'أسوان': 10.5,
            'البحر الأحمر': 10.0,
        }

        daily_hours = sun_hours.get(region, 9.5)
        system_kw = (panel_count * panel_watts) / 1000
        daily_energy = system_kw * daily_hours * 0.75
        yearly_energy = daily_energy * 365

        return int(yearly_energy)

    def _economic_analysis(self, design_option, monthly_consumption, region):
        """تحليل اقتصادي للتصميم"""
        yearly_energy = design_option['estimated_yearly_energy_kwh']
        cost = design_option['estimated_cost_egp']

        energy_value = yearly_energy * self.egyptian_factors['electricity_price']
        yearly_consumption = monthly_consumption * 12
        bill_saving = min(energy_value, yearly_consumption * self.egyptian_factors['electricity_price'])

        payback_period = cost / bill_saving if bill_saving > 0 else 20

        ten_year_savings = bill_saving * 10
        maintenance_cost = cost * self.egyptian_factors['maintenance_cost'] * 10
        net_savings = ten_year_savings - maintenance_cost

        roi_percentage = ((net_savings - cost) / cost) * 100 if cost > 0 else 0
        roi_score = min(100, max(0, roi_percentage / 2))

        return {
            'initial_cost_egp': cost,
            'yearly_savings_egp': int(bill_saving),
            'payback_period_years': round(payback_period, 1),
            'roi_10_years_percent': round(roi_percentage, 1),
            'roi_score': int(roi_score),
            'recommendation': self._get_recommendation(roi_score, payback_period)
        }

    def _get_recommendation(self, roi_score, payback_period):
        """توليد توصية بناءً على النتائج"""
        if roi_score >= 80:
            return "استثمار ممتاز - موصى به بشدة"
        elif roi_score >= 60:
            return "استثمار جيد - موصى به"
        elif roi_score >= 40:
            return "استثمار مقبول - ضع في الاعتبار"
        elif payback_period <= 5:
            return "فترة استرداد جيدة - يمكن النظر فيه"
        else:
            return "يحتاج دراسة أكثر - قد لا يكون اقتصادياً"

    def _get_regional_dust_factor(self, region):
        """عامل الغبار الإقليمي"""
        dust_factors = {
            'القاهرة': 0.94,
            'الإسكندرية': 0.97,
            'أسوان': 0.91,
            'البحر الأحمر': 0.93,
        }
        return dust_factors.get(region, 0.95)

    def _get_temperature_impact(self, region):
        """تأثير درجة الحرارة على كفاءة الألواح"""
        temp_impacts = {
            'القاهرة': 0.97,
            'الإسكندرية': 0.98,
            'أسوان': 0.95,
            'البحر الأحمر': 0.96,
        }
        return temp_impacts.get(region, 0.97)
