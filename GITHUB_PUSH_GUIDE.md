# 📝 GITHUB PUSH CHECKLIST

## ✅ Hazırlık Kontrolleri

### 1. Kritik Dosyalar Kontrolü

```bash
# .env dosyası GitHub'da olmamalı!
git status

# Eğer .env görünüyorsa:
git rm --cached .env
git commit -m "Remove .env from git"
```

### 2. .gitignore Doğrulama

Aşağıdaki dosyaların .gitignore'da olduğundan emin olun:
- `.env`
- `.env.local`
- `config.py`
- `*.log`
- `__pycache__/`

### 3. Secrets Temizliği

```bash
# API keys hiçbir dosyada hardcoded olmamalı
# Kontrol et:
grep -r "BINANCE_API_KEY" --exclude-dir=.git --exclude=*.md --exclude=.env.sample

# Eğer herhangi bir dosyada görünüyorsa, temizle!
```

## 🚀 GitHub Push Adımları

### Windows PowerShell

```powershell
# 1. Git durumunu kontrol et
git status

# 2. Değişiklikleri ekle (.env hariç - otomatik .gitignore)
git add .

# 3. Commit oluştur
git commit -m "Ready for Northflank deployment - Pump & Dump Bot v3"

# 4. Branch kontrol (main olmalı)
git branch

# 5. Remote kontrol (GitHub repo URL)
git remote -v

# 6. Eğer remote yoksa ekle:
# git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git

# 7. Push
git push origin main

# İlk push ise:
# git push -u origin main
```

### Alternatif: Linux/Mac Terminal

```bash
# Aynı komutlar çalışır
git add .
git commit -m "Ready for Northflank deployment - Pump & Dump Bot v3"
git push origin main
```

## 🔒 Güvenlik Final Check

### Push Öncesi Son Kontrol

```powershell
# 1. .env dosyası staged değil mi?
git diff --cached --name-only | Select-String ".env"
# BOŞTA DÖNMELI (hiçbir .env dosyası olmamalı)

# 2. API keys commit'lenmemiş mi?
git log --all --full-history -- .env
git log --all --full-history -- config.py
# "fatal: ambiguous argument" DÖNMELI (dosya hiç commit'lenmedi)

# 3. Son commit'i kontrol et
git show --stat
# .env veya config.py listede OLMAMALI
```

## 📊 Push Sonrası

### GitHub'da Kontrol

1. Repository sayfasına git
2. Files kontrol et:
   - ✅ `18.02.2026.py` var
   - ✅ `Dockerfile` var
   - ✅ `.env.sample` var
   - ❌ `.env` YOK (olmamalı!)
   - ❌ `config.py` YOK (olmamalı!)

3. `.gitignore` çalışıyor mu?
   - Logs/ klasörü yok
   - __pycache__/ klasörü yok

## 🌐 Northflank Deployment

Push başarılı olduktan sonra:

1. **Northflank'a git**: https://northflank.com
2. **New Project** → Repository seç
3. **Environment Variables** ekle:
   ```
   BINANCE_API_KEY=your_demo_key
   BINANCE_API_SECRET=your_demo_secret
   DEMO_MODE=true
   AUTO_LIVE_MODE=true
   ```
4. **Build & Deploy**

Detaylar: [NORTHFLANK_DEPLOYMENT.md](NORTHFLANK_DEPLOYMENT.md)

## 🐛 Yaygın Hatalar

### "remote rejected" hatası

```bash
# Repository URL'i kontrol et
git remote -v

# Yanlışsa düzelt:
git remote set-url origin https://github.com/USERNAME/REPO.git
```

### "Please tell me who you are" hatası

```bash
# Git config ayarla
git config --global user.email "your@email.com"
git config --global user.name "Your Name"
```

### ".env pushed accidentally"

```bash
# HEMEN GERİ AL!
git rm --cached .env
git commit -m "Remove .env from repository"
git push origin main

# GitHub'da:
# Settings → Secrets → Repository secrets → API keys'i değiştir!
```

## ✅ Push Tamamlandı!

Başarılı push sonrası:
- [ ] GitHub'da dosyalar görünüyor
- [ ] .env ve config.py yok
- [ ] README.md güncel
- [ ] Dockerfile mevcut
- [ ] Northflank'da deploy edilebilir

## 📞 Yardım

Sorun yaşıyorsanız:
- GitHub docs: https://docs.github.com
- Northflank support: https://northflank.com/support
- Issues: Repository → Issues sekmesi

---

**Hazır mısınız? Hadi başlayalım!**

```bash
git add .
git commit -m "🚀 Pump & Dump Bot v3 - Production Ready"
git push origin main
```
