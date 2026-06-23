import os
import cv2
import glob
import numpy as np

def main():
    # البحث عن مجلد الصور
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'datasets', 'egyptian_roofs'))
    img_dir = os.path.join(base_dir, 'images', 'train')
    lbl_dir = os.path.join(base_dir, 'labels', 'train')
    
    images = glob.glob(os.path.join(img_dir, '*.jpg'))
    if not images:
        print("❌ لم يتم العثور على أي صور. قم بتوليد الداتا أولاً.")
        return
        
    # فحص أول 5 صور
    for i, img_path in enumerate(images[:5]):
        img = cv2.imread(img_path)
        h, w = img.shape[:2]
        
        lbl_path = os.path.join(lbl_dir, os.path.basename(img_path).replace('.jpg', '.txt'))
        if not os.path.exists(lbl_path):
            continue
            
        overlay = img.copy()
        with open(lbl_path, 'r') as f:
            for line in f:
                parts = list(map(float, line.strip().split()))
                cls_id = int(parts[0])
                coords = parts[1:]
                
                # تحويل الإحداثيات النسبية إلى بكسلات
                pts = []
                for j in range(0, len(coords), 2):
                    x = int(coords[j] * w)
                    y = int(coords[j+1] * h)
                    pts.append([x, y])
                    
                pts_np = np.array(pts, dtype=np.int32).reshape((-1, 1, 2))
                
                # اللون الأخضر للسطح، والأحمر للعوائق
                color = (0, 255, 0) if cls_id == 0 else (0, 0, 255)
                
                # رسم الحواف
                cv2.polylines(overlay, [pts_np], True, color, 2)
                # تعبئة بلون شفاف (Alpha blend)
                cv2.fillPoly(overlay, [pts_np], color)
                
        # دمج الـ Mask مع الصورة الأصلية بنسبة 50%
        blended = cv2.addWeighted(img, 0.6, overlay, 0.4, 0)
        
        # حفظ النتيجة لمعاينتها
        out_path = f"sanity_check_{i}.jpg"
        cv2.imwrite(out_path, blended)
        print(f"✅ تم حفظ صورة الفحص البصري: {out_path}")

if __name__ == "__main__":
    main()
