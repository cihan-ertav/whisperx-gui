import os
import glob
import gc
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
import torch
import whisperx
from whisperx.diarize import DiarizationPipeline

# --- FFmpeg Ortam Değişkeni Desteği ---
ffmpeg_base = os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Packages")
ffmpeg_matches = glob.glob(os.path.join(ffmpeg_base, "*FFmpeg*", "*", "bin"))
if ffmpeg_matches and os.path.exists(ffmpeg_matches[0]):
    os.environ["PATH"] += os.pathsep + ffmpeg_matches[0]


def format_timestamp(seconds: float) -> str:
    """Saniyeyi [DD:SS] veya [SS:DD:SS] formatına dönüştürür."""
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


class WhisperXApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("WhisperX Konuşmacı Ayrıştırma (RTX Hızlandırmalı)")
        self.geometry("750x730")
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.selected_file = None

        # Başlık
        self.lbl_title = ctk.CTkLabel(
            self,
            text="Ses Transkript & Diyalog Aracı",
            font=ctk.CTkFont(size=20, weight="bold")
        )
        self.lbl_title.pack(pady=(20, 15))

        # HF Token Bölümü
        self.frame_token = ctk.CTkFrame(self)
        self.frame_token.pack(fill="x", padx=30, pady=5)

        self.lbl_token = ctk.CTkLabel(self.frame_token, text="HF Token:", font=ctk.CTkFont(size=13))
        self.lbl_token.pack(side="left", padx=10, pady=10)

        self.entry_token = ctk.CTkEntry(
            self.frame_token,
            placeholder_text="Hugging Face User Access Token (hf_...)",
            width=500
        )
        self.entry_token.pack(side="left", padx=10, pady=10, fill="x", expand=True)

        # Donanım & Performans Ayarları
        self.frame_hardware = ctk.CTkFrame(self)
        self.frame_hardware.pack(fill="x", padx=30, pady=5)

        self.lbl_profile = ctk.CTkLabel(self.frame_hardware, text="Sistem Profili:", font=ctk.CTkFont(size=13))
        self.lbl_profile.grid(row=0, column=0, padx=10, pady=10, sticky="w")

        self.opt_profile = ctk.CTkOptionMenu(
            self.frame_hardware,
            values=["Düşük/Orta VRAM (3050 Ti - Boşaltmalı)", "Yüksek VRAM (RTX 5070 / 12GB+)"],
            command=self.on_profile_change
        )
        self.opt_profile.set("Düşük/Orta VRAM (3050 Ti - Boşaltmalı)")
        self.opt_profile.grid(row=0, column=1, padx=10, pady=10, sticky="ew")

        self.lbl_batch = ctk.CTkLabel(self.frame_hardware, text="Batch Size:", font=ctk.CTkFont(size=13))
        self.lbl_batch.grid(row=0, column=2, padx=10, pady=10, sticky="w")

        self.opt_batch = ctk.CTkOptionMenu(
            self.frame_hardware,
            values=["4", "8", "16", "32"],
            width=80
        )
        self.opt_batch.set("4")
        self.opt_batch.grid(row=0, column=3, padx=10, pady=10, sticky="ew")

        self.frame_hardware.grid_columnconfigure((1, 3), weight=1)

        # Dosya Seçim Bölümü
        self.frame_file = ctk.CTkFrame(self)
        self.frame_file.pack(fill="x", padx=30, pady=10)

        self.btn_select = ctk.CTkButton(
            self.frame_file,
            text="Ses Dosyası Seç",
            command=self.select_file,
            width=140
        )
        self.btn_select.pack(side="left", padx=10, pady=10)

        self.lbl_file = ctk.CTkLabel(
            self.frame_file,
            text="Henüz dosya seçilmedi...",
            text_color="gray",
            anchor="w"
        )
        self.lbl_file.pack(side="left", padx=10, pady=10, fill="x", expand=True)

        # Başlat Butonu
        self.btn_start = ctk.CTkButton(
            self,
            text="Transkripti Başlat",
            command=self.start_processing_thread,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#1f7a1f",
            hover_color="#145214",
            height=40
        )
        self.btn_start.pack(fill="x", padx=30, pady=10)

        # Durum ve İlerleme
        self.lbl_status = ctk.CTkLabel(self, text="Hazır", font=ctk.CTkFont(size=13))
        self.lbl_status.pack(pady=(10, 5))

        self.progress = ctk.CTkProgressBar(self, width=690)
        self.progress.set(0)
        self.progress.pack(pady=5)

        # Metin Sonuç Alanı
        self.textbox = ctk.CTkTextbox(self, width=690, height=290, font=ctk.CTkFont(size=13))
        self.textbox.pack(padx=30, pady=(10, 20), fill="both", expand=True)

    def on_profile_change(self, choice):
        if "5070" in choice:
            self.opt_batch.set("16")
        else:
            self.opt_batch.set("4")

    def select_file(self):
        file_path = filedialog.askopenfilename(
            filetypes=[("Ses Dosyaları", "*.mp3 *.wav *.m4a *.flac *.aac *.ogg"), ("Tüm Dosyalar", "*.*")]
        )
        if file_path:
            self.selected_file = file_path
            self.lbl_file.configure(text=os.path.basename(file_path), text_color="white")

    def update_status(self, text, progress_val):
        self.lbl_status.configure(text=text)
        self.progress.set(progress_val)
        self.update_idletasks()

    def start_processing_thread(self):
        if not self.selected_file:
            messagebox.showwarning("Uyarı", "Lütfen önce bir ses dosyası seçin!")
            return

        token = self.entry_token.get().strip()
        if not token:
            messagebox.showwarning("Uyarı", "Lütfen Hugging Face Access Token bilginizi girin!")
            return

        self.btn_start.configure(state="disabled")
        self.btn_select.configure(state="disabled")
        self.textbox.delete("1.0", "end")

        thread = threading.Thread(target=self.process_audio, args=(token,), daemon=True)
        thread.start()

    def process_audio(self, token):
        try:
            # 1. Donanım ve Profil Ayarları
            selected_profile = self.opt_profile.get()
            batch_size = int(self.opt_batch.get())
            empty_vram = "Düşük" in selected_profile

            is_cuda = torch.cuda.is_available()
            device = "cuda" if is_cuda else "cpu"
            compute_type = "float16" if is_cuda else "int8"

            # 2. Transkripsiyon (Whisper large-v3)
            self.update_status(f"1/3 Transkripsiyon (Large-v3, Batch: {batch_size})...", 0.2)
            model = whisperx.load_model("large-v3", device, compute_type=compute_type)
            audio = whisperx.load_audio(self.selected_file)
            result = model.transcribe(audio, batch_size=batch_size)

            if empty_vram:
                del model
                gc.collect()
                if is_cuda:
                    torch.cuda.empty_cache()

            # 3. Kelime Hizalama (Wav2Vec2)
            detected_lang = result.get("language", "tr")
            if detected_lang not in ["tr", "en"]:
                detected_lang = "tr"

            self.update_status(f"2/3 Kelime zamanlamaları hizalanıyor ({detected_lang.upper()})...", 0.5)
            try:
                model_a, metadata = whisperx.load_align_model(language_code=detected_lang, device=device)
                result = whisperx.align(result["segments"], model_a, metadata, audio, device, return_char_alignments=False)
                if empty_vram:
                    del model_a
                    gc.collect()
                    if is_cuda:
                        torch.cuda.empty_cache()
            except Exception as align_err:
                print(f"Hizalama uyarısı (atlandı): {align_err}")

            # 4. Konuşmacı Ayrıştırma (GPU)
            self.update_status("3/3 Konuşmacılar ayrıştırılıyor (GPU)...", 0.8)
            diarize_model = DiarizationPipeline(token=token, device=device)
            diarize_segments = diarize_model(audio)
            result = whisperx.assign_word_speakers(diarize_segments, result)

            if empty_vram:
                del diarize_model
                gc.collect()
                if is_cuda:
                    torch.cuda.empty_cache()

            # 5. Çıktı Formatlama ve Arayüze Yazma
            output_lines = []
            for seg in result["segments"]:
                start_time = format_timestamp(seg.get("start", 0))
                end_time = format_timestamp(seg.get("end", 0))
                speaker = seg.get("speaker", "Bilinmeyen")
                text = seg.get("text", "").strip()

                line = f"[{start_time} - {end_time}] [{speaker}]: {text}\n"
                output_lines.append(line)
                self.textbox.insert("end", line)

            # Metin belgesine kaydet
            txt_path = os.path.splitext(self.selected_file)[0] + "_diyalog.txt"
            with open(txt_path, "w", encoding="utf-8") as f:
                f.writelines(output_lines)

            self.update_status("Tamamlandı!", 1.0)
            messagebox.showinfo("Başarılı", f"İşlem tamamlandı!\nSonuçlar kaydedildi:\n{txt_path}")

        except Exception as e:
            import traceback
            print("\n--- HATA DETAYI BAŞLANGICI ---")
            traceback.print_exc()
            print("--- HATA DETAYI BİTİŞİ ---\n")
            self.update_status("Hata oluştu!", 0)
            messagebox.showerror("Hata", str(e))

        finally:
            self.btn_start.configure(state="normal")
            self.btn_select.configure(state="normal")


if __name__ == "__main__":
    app = WhisperXApp()
    app.mainloop()