@echo off
chcp 65001 > nul
echo ===================================================
echo WhisperX Kurulumu Başlatılıyor (RTX Destekli)
echo ===================================================

echo 1. Python 3.11 ile Sanal Ortam (.venv) Oluşturuluyor...

:: Öncelikli olarak py -3.11 ile oluşturmayı dener (3.14'ü baypas eder)
py -3.11 -m venv .venv 2>nul
if errorlevel 1 (
    echo [UYARI] 'py -3.11' bulunamadi, varsayilan python deneniyor...
    python -m venv .venv
)

if not exist .venv\Scripts\activate.bat (
    echo [HATA] Sanal ortam olusturulamadi!
    echo Lutfen sistemde Python 3.11 yuklu oldugundan emin olun.
    pause
    exit /b 1
)

call .venv\Scripts\activate

echo.
echo Aktif Python Surumu:
python --version
echo.

echo 2. Pip Güncelleniyor...
python -m pip install --upgrade pip

echo 3. CUDA Destekli PyTorch (cu124) Kuruluyor...
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124

echo 4. Gerekli Kütüphaneler Kuruluyor...
pip install -r requirements.txt

echo ===================================================
echo Kurulum Tamamlandı! Artık calistir.bat ile açabilirsiniz.
echo ===================================================
pause