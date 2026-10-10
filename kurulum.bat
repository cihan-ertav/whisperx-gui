@echo off
chcp 65001 > nul
echo ===================================================
echo WhisperX Kurulumu Başlatılıyor (RTX Destekli)
echo ===================================================

echo 1. Python Sanal Ortamı (.venv) Oluşturuluyor...
python -m venv .venv
call .venv\Scripts\activate

echo 2. Pip Güncelleniyor...
python -m pip install --upgrade pip

echo 3. CUDA Destekli PyTorch Kuruluyor...
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124

echo 4. Gerekli Kütüphaneler Kuruluyor...
pip install -r requirements.txt

echo ===================================================
echo Kurulum Tamamlandı! Artık calistir.bat ile açabilirsiniz.
echo ===================================================
pause