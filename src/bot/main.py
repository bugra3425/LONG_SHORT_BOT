"""
==============================================================================
PUMP & DUMP REVERSION BOT — ANA GİRİŞ NOKTASI
Tarih : 18 Şubat 2026
Geliştirici: Buğra Türkoğlu
18.02.2026.py ana dosyasını çalıştırır
==============================================================================
"""
import sys
from pathlib import Path

# Proje kökünü Python path'e ekle
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

def main():
    """
    Ana giriş noktası - 18.02.2026.py dosyasını çalıştırır
    """
    # 18.02.2026.py dosyasını import et ve main() fonksiyonunu çalıştır
    try:
        from importlib.machinery import SourceFileLoader
        
        main_file_path = project_root / "18.02.2026.py"
        
        if not main_file_path.exists():
            print(f"❌ Ana strateji dosyası bulunamadı: {main_file_path}")
            print("Lütfen 18.02.2026.py dosyasının proje kökünde olduğundan emin olun.")
            sys.exit(1)
        
        # Dosyayı modül olarak yükle
        loader = SourceFileLoader("main_strategy", str(main_file_path))
        main_module = loader.load_module()
        
        # main() fonksiyonunu çalıştır
        if hasattr(main_module, 'main'):
            main_module.main()
        else:
            print("❌ main() fonksiyonu 18.02.2026.py dosyasında bulunamadı!")
            sys.exit(1)
            
    except Exception as e:
        print(f"❌ Hata oluştu: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
