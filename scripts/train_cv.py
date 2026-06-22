import os
import shutil
import sys
from pathlib import Path

# إعداد المسار الجذري للمشروع للتمكن من قراءة مجلد ai_engine
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, PROJECT_ROOT)

from ai_engine.computer_vision.dataset_creator import YOLODatasetCreator

def main():
    print("="*50)
    print("1. إنشاء مجموعة البيانات الاصطناعية (Synthetic Dataset)")
    print("="*50)
    # سنقوم بتوليد 2000 صورة للتدريب و 400 للاختبار للحصول على دقة مقبولة
    # يتم الحفظ بداخل مجلد datasets/egyptian_roofs
    dataset_path = os.path.join(PROJECT_ROOT, 'datasets', 'egyptian_roofs')
    creator = YOLODatasetCreator(dataset_root=dataset_path)
    stats = creator.generate_synthetic_roof_dataset(n_train=2000, n_val=400, image_size=640)
    print(f"✅ تمت تهيئة مجموعة البيانات بنجاح في: {stats['dataset_root']}")

    print("\n" + "="*50)
    print("2. بدء تدريب نموذج YOLOv8 Segmentation")
    print("="*50)
    try:
        from ultralytics import YOLO
    except ImportError:
        print("❌ خطأ: مكتبة ultralytics غير منصبة.")
        print("قم بتشغيل الأمر التالي في التيرمنال: pip install ultralytics")
        sys.exit(1)

    # تحميل النموذج المبدئي
    model = YOLO('yolov8n-seg.pt')

    data_yaml_path = os.path.abspath(os.path.join(stats['dataset_root'], 'data.yaml'))
    
    # عملية التدريب
    print(f"📄 استخدام ملف البيانات: {data_yaml_path}")
    results = model.train(
        data=data_yaml_path,
        epochs=50,          # 50 دورة تدريبية مناسبة للبيانات الاصطناعية (يمكنك زيادتها إذا لزم الأمر)
        imgsz=640,
        batch=16,
        name='shamsi_roof_model',
        device='',          # سيقوم باستخدام الـ GPU تلقائياً إن وُجد
        workers=4,
    )

    print("\n" + "="*50)
    print("3. استخراج أفضل نموذج وربطه بالنظام")
    print("="*50)
    
    # مسار حفظ أفضل نتيجة من عملية التدريب الحالية
    # تقوم Ultralytics بحفظ النتائج في مجلد runs/segment بشكل افتراضي
    best_weights = Path(os.path.join(PROJECT_ROOT, 'runs', 'segment', 'shamsi_roof_model', 'weights', 'best.pt'))
    
    if best_weights.exists():
        target_dir = Path(os.path.join(PROJECT_ROOT, 'ai_engine', 'models'))
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / 'roof_detector_best.pt'
        
        # نسخ الملف للمكان الصحيح في النظام ليتعرف عليه المودل
        shutil.copy2(best_weights, target_path)
        print(f"🎉 نجاح! تم نسخ النموذج الجاهز إلى: {target_path}")
        print("يمكنك الآن استخدام الـ API وتحليل أسطح المنازل من الأقمار الصناعية.")
    else:
        print("⚠️ تحذير: لم يتم العثور على ملف best.pt. تأكد من إكمال عملية التدريب بدون أخطاء.")
        print(f"بحثنا عنه في: {best_weights}")

if __name__ == "__main__":
    main()
