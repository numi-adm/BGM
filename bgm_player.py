import customtkinter as ctk
from tkinter import messagebox
import os
import sys
from pathlib import Path
import threading
import winreg
import time
import subprocess
import tempfile
import glob
import random
import pystray
from PIL import Image, ImageDraw, ImageFont
import watchdog.observers
import watchdog.events
import json
from datetime import datetime

# ค่าคงที่สำหรับซ่อนหน้าต่าง CMD/PowerShell ใน Windows
CREATE_NO_WINDOW = 0x08000000

class BGMPlayer:
    def __init__(self, root):
        self.root = root
        self.root.title("BGM Player")
        self.root.geometry("700x850")
        self.root.resizable(False, False)
        
        # ตั้งค่า Icon ของหน้าต่างโปรแกรม (ถ้ามีไฟล์ icon.ico)
        icon_path = self.resource_path("icon.ico")
        if os.path.exists(icon_path):
            self.root.iconbitmap(icon_path)
        
        # Set CustomTkinter theme
        ctk.set_appearance_mode("Light")
        ctk.set_default_color_theme("blue")
        
        # ตั้งค่าฟอนต์
        self.font_title = ("Alex Brush", 28, "bold")
        self.font_header = ("Alex Brush", 22, "bold")
        self.font_normal = ("Alex Brush", 18)
        self.font_small = ("Alex Brush", 16)
        self.font_button = ("Alex Brush", 18, "bold")
        
        # สีพาสเทลนุ่มนิ่ม
        self.colors = {
            'bg': "#FFF5E6",
            'card': "#FFFFFF",
            'primary': "#FFB5B5",
            'secondary': "#B5D8FF",
            'accent': "#FFE4B5",
            'success': "#B5E8B5",
            'danger': "#FFB5B5",
            'text': "#5C5C5C",
            'text_dark': "#3C3C3C",
            'border': "#FFE4E1",
            'save': "#FFD4A8", 
        }
        
        # จัดการ Path สำหรับโหมด .exe
        if getattr(sys, 'frozen', False):
            self.base_dir = os.path.dirname(sys.executable)
        else:
            self.base_dir = os.path.dirname(os.path.abspath(__file__))
            
        self.settings_file = os.path.join(self.base_dir, "settings.json")
        
        # ตัวแปรสำหรับจัดการเพลง
        self.is_playing = False
        self.is_muted = False
        self.play_thread = None
        self.stop_event = threading.Event()
        self.current_process = None
        self.temp_wav_path = None
        self.restart_flag = threading.Event()
        
        self.seek_position = 0
        self.current_play_time = 0
        
        self.song_duration = 0
        self.current_file = None
        
        # ตัวแปรระบบหน่วงเวลา
        self._vol_timer = None
        self._speed_timer = None
        self._seek_timer = None
        
        # ตัวแปรสำหรับเก็บค่าชั่วคราว
        self.temp_volume = None
        self.temp_speed = None
        self.temp_mode = None
        
        # Load settings
        self.load_settings()
        
        # เส้นทางไฟล์เพลง
        self.bgm_dir = os.path.join(self.base_dir, "BGM")
        
        if not os.path.exists(self.bgm_dir):
            os.makedirs(self.bgm_dir)
            
        self.mp3_files = glob.glob(os.path.join(self.bgm_dir, "*.mp3"))
        self.selected_files = []
        self.current_file_index = 0
        
        # Find ffmpeg path
        self.ffmpeg_path = self.find_ffmpeg()
        
        # ตั้งค่าสีพื้นหลัง
        self.root.configure(fg_color=self.colors['bg'])
        
        # สร้าง UI
        self.create_widgets()
        
        # System tray icon
        self.tray_icon = None
        self.setup_system_tray()
        
        # File watcher for auto-refresh
        self.setup_file_watcher()
        
        # ตั้งค่า event handler สำหรับปิดหน้าต่าง
        self.root.protocol("WM_DELETE_WINDOW", self.on_minimize_to_tray)
        
        # ==========================================
        # เพิ่มระบบเล่นอัตโนมัติเมื่อเปิดโปรแกรม
        # ==========================================
        self.select_all_songs() # เลือกเพลงทั้งหมดอัตโนมัติ
        if self.mp3_files and self.ffmpeg_path:
            # หน่วงเวลา 0.5 วินาทีให้ UI โหลดเสร็จก่อน แล้วสั่งเล่นเพลง
            self.root.after(500, self.start_playback)
        
    def resource_path(self, relative_path):
        """รับ Path ที่ถูกต้องเสมอ ไม่ว่าจะรันผ่าน .py หรือ .exe ที่ถูก Build แบบ onefile"""
        try:
            base_path = sys._MEIPASS
        except Exception:
            base_path = os.path.abspath(".")
        return os.path.join(base_path, relative_path)
    
    def load_settings(self):
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                    self.volume = settings.get('volume', 1.0)
                    self.playback_speed = settings.get('playback_speed', 1.0)
                    self.playback_mode = settings.get('playback_mode', 'loop')
                    self.is_muted = settings.get('is_muted', False)
                    
                    self.temp_volume = self.volume
                    self.temp_speed = self.playback_speed
                    self.temp_mode = self.playback_mode
            else:
                self._set_default_settings()
        except Exception:
            self._set_default_settings()

    def _set_default_settings(self):
        self.volume = 1.0
        self.playback_speed = 1.0
        self.playback_mode = "loop"
        self.is_muted = False
        self.temp_volume = self.volume
        self.temp_speed = self.playback_speed
        self.temp_mode = self.playback_mode
    
    def save_settings(self):
        try:
            settings = {
                'volume': self.volume,
                'playback_speed': self.playback_speed,
                'playback_mode': self.playback_mode,
                'is_muted': self.is_muted
            }
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(settings, f, indent=4)
            return True
        except Exception:
            return False
    
    def save_audio_settings(self):
        self.volume = self.temp_volume if self.temp_volume is not None else self.volume
        self.playback_speed = self.temp_speed if self.temp_speed is not None else self.playback_speed
        self.playback_mode = self.temp_mode if self.temp_mode is not None else self.playback_mode
        
        if self.save_settings():
            self.show_save_confirmation()
            self.apply_audio_changes()
        else:
            messagebox.showerror("ข้อผิดพลาด", "ไม่สามารถบันทึกการตั้งค่าได้")
    
    def show_save_confirmation(self):
        self.save_button.configure(
            text="✓ บันทึกแล้ว!",
            fg_color="#B5E8B5",
            hover_color="#9ED89E",
            border_color="#A8D8A8"
        )
        self.root.after(2000, self.reset_save_button)
    
    def reset_save_button(self):
        self.save_button.configure(
            text="💾 บันทึกการตั้งค่า",
            fg_color=self.colors['save'],
            hover_color="#FFC888",
            border_color="#FFD4A8"
        )
    
    def find_ffmpeg(self):
        try:
            # เพิ่ม CREATE_NO_WINDOW เพื่อไม่ให้เด้งหน้าต่างสีดำ
            result = subprocess.run(['where', 'ffmpeg'], capture_output=True, text=True, timeout=2, creationflags=CREATE_NO_WINDOW)
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip().split('\n')[0]
        except:
            pass
        
        possible_paths = [
            r"C:\Users\NuMI\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.1-full_build\bin\ffmpeg.exe",
            r"C:\ffmpeg\bin\ffmpeg.exe",
            r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
            r"C:\Program Files (x86)\ffmpeg\bin\ffmpeg.exe",
        ]
        
        for path in possible_paths:
            if os.path.exists(path):
                return path
        return None
    
    def setup_system_tray(self):
        try:
            icon_path = self.resource_path("icon.ico")
            
            if os.path.exists(icon_path):
                image = Image.open(icon_path)
            else:
                image = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
                draw = ImageDraw.Draw(image)
                draw.ellipse([6, 6, 58, 58], fill="#FFB5B5", outline="#FF8A8A", width=3)
                draw.ellipse([16, 38, 24, 46], fill="#FFFFFF", outline="#FFE4E1", width=2)
                draw.ellipse([32, 38, 40, 46], fill="#FFFFFF", outline="#FFE4E1", width=2)
                draw.rectangle([22, 16, 24, 44], fill="#FFFFFF", outline="#FFE4E1", width=2)
                draw.rectangle([38, 16, 40, 44], fill="#FFFFFF", outline="#FFE4E1", width=2)
                draw.rectangle([22, 16, 40, 20], fill="#FFFFFF", outline="#FFE4E1", width=2)
            
            menu = pystray.Menu(
                pystray.MenuItem("แสดงหน้าต่าง", self.show_window, default=True),
                pystray.MenuItem("เล่น/หยุด", self.toggle_playback_from_tray),
                pystray.MenuItem("ปิด/เปิดเสียง", self.toggle_mute_from_tray),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("ออกจากโปรแกรม", self.exit_application)
            )
            
            self.tray_icon = pystray.Icon("BGM Player", image, "BGM Player", menu)
            threading.Thread(target=self.tray_icon.run, daemon=True).start()
        except Exception as e:
            print(f"System tray error: {e}")
    
    def setup_file_watcher(self):
        try:
            class MusicFileHandler(watchdog.events.FileSystemEventHandler):
                def __init__(self, player):
                    self.player = player
                    self.last_update = 0
                
                def on_any_event(self, event):
                    if not event.is_directory and event.src_path.endswith('.mp3'):
                        current_time = time.time()
                        if current_time - self.last_update > 2:
                            self.last_update = current_time
                            self.player.refresh_song_list()
            
            event_handler = MusicFileHandler(self)
            observer = watchdog.observers.Observer()
            observer.schedule(event_handler, self.bgm_dir, recursive=False)
            observer.start()
        except Exception as e:
            print(f"File watcher error: {e}")
    
    def refresh_song_list(self):
        self.mp3_files = glob.glob(os.path.join(self.bgm_dir, "*.mp3"))
        self.root.after(0, self.rebuild_song_list)
    
    def rebuild_song_list(self):
        selected_filenames = set()
        if hasattr(self, 'song_vars'):
            for i, var in enumerate(self.song_vars):
                if i < len(self.mp3_files) and var.get():
                    selected_filenames.add(os.path.basename(self.mp3_files[i]))
        
        for widget in self.song_frame.winfo_children():
            widget.destroy()
        
        self.song_vars = []
        if self.mp3_files:
            for i, mp3_file in enumerate(self.mp3_files):
                filename = os.path.basename(mp3_file)
                var = ctk.BooleanVar(value=(filename in selected_filenames))
                self.song_vars.append(var)
                
                row_frame = ctk.CTkFrame(self.song_frame, fg_color="#FFF9F0", corner_radius=15, border_width=1, border_color=self.colors['border'])
                row_frame.pack(fill="x", pady=3, padx=5)
                
                check = ctk.CTkCheckBox(row_frame, text=filename, variable=var, font=self.font_normal, checkbox_width=22, checkbox_height=22, corner_radius=8, border_width=2, border_color=self.colors['primary'], fg_color=self.colors['primary'], hover_color=self.colors['accent'], checkmark_color="white", text_color=self.colors['text_dark'])
                check.pack(side="left", padx=10, pady=5)
                
                duration = self.get_audio_duration(mp3_file)
                if duration > 0:
                    mins, secs = divmod(int(duration), 60)
                    ctk.CTkLabel(row_frame, text=f"{mins}:{secs:02d}", font=self.font_small, text_color="#B8B8B8").pack(side="right", padx=15)
        else:
            ctk.CTkLabel(self.song_frame, text="📁 ไม่พบไฟล์ MP3 ในโฟลเดอร์ BGM\nวางไฟล์เพลง .mp3 ลงในโฟลเดอร์ BGM", font=self.font_normal, text_color="#E8A0A0", justify="center").pack(pady=30)
    
    def get_audio_duration(self, filepath):
        try:
            ffprobe_path = self.ffmpeg_path.replace('ffmpeg.exe', 'ffprobe.exe')
            if os.path.exists(ffprobe_path):
                probe_cmd = [ffprobe_path, '-i', filepath, '-show_entries', 'format=duration', '-v', 'quiet', '-of', 'csv=p=0']
                # ซ่อนหน้าต่าง
                result = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=3, creationflags=CREATE_NO_WINDOW)
                if result.stdout.strip():
                    return float(result.stdout.strip())
        except:
            pass
        return 0
    
    def show_window(self, icon=None, item=None):
        self.root.deiconify()
        self.root.lift()
        self.root.focus()
    
    def toggle_playback_from_tray(self, icon=None, item=None):
        self.root.after(0, self.toggle_playback)
    
    def toggle_mute_from_tray(self, icon=None, item=None):
        self.root.after(0, self.toggle_mute)
    
    def on_minimize_to_tray(self):
        self.root.withdraw()
        if self.tray_icon:
            try:
                self.tray_icon.notify("BGM Player ยังคงทำงานอยู่", "คลิกที่ไอคอนเพื่อเปิดหน้าต่าง")
            except:
                pass
    
    def open_music_folder(self):
        try:
            os.startfile(self.bgm_dir)
        except Exception as e:
            messagebox.showerror("ข้อผิดพลาด", f"ไม่สามารถเปิดโฟลเดอร์ได้: {e}")
    
    def create_widgets(self):
        self.main_container = ctk.CTkFrame(self.root, fg_color=self.colors['bg'], corner_radius=20)
        self.main_container.pack(fill="both", expand=True, padx=15, pady=15)
        
        header_frame = ctk.CTkFrame(self.main_container, fg_color="#FFF9F0", corner_radius=25, border_width=2, border_color=self.colors['border'])
        header_frame.pack(fill="x", pady=(0, 15), padx=10)
        
        ctk.CTkLabel(header_frame, text="🎵 BGM Player", font=self.font_title, text_color=self.colors['text_dark']).pack(pady=15)
        
        self.status_label = ctk.CTkLabel(header_frame, text="เลือกเพลงแล้วกดเล่น", font=self.font_normal, text_color="#E8A0A0")
        self.status_label.pack(pady=(0, 15))
        
        self.scrollable_frame = ctk.CTkScrollableFrame(self.main_container, fg_color="transparent", corner_radius=15)
        self.scrollable_frame.pack(fill="both", expand=True, padx=5)
        
        if not self.ffmpeg_path:
            warning_frame = ctk.CTkFrame(self.scrollable_frame, fg_color="#FFE4E1", corner_radius=15, border_width=2, border_color="#FFB5B5")
            warning_frame.pack(fill="x", pady=(0, 15), padx=10)
            ctk.CTkLabel(warning_frame, text="⚠️ ไม่พบ FFmpeg กรุณาติดตั้ง FFmpeg ก่อนใช้งาน", font=self.font_normal, text_color="#E87474").pack(pady=15)
        
        song_card = self.create_hand_drawn_card("🎶 เลือกเพลง", "เลือกเพลงที่ต้องการเล่น")
        button_row = ctk.CTkFrame(song_card, fg_color="transparent")
        button_row.pack(fill="x", padx=15, pady=(5, 10))
        
        ctk.CTkButton(button_row, text="📂 เปิดโฟลเดอร์เพลง", command=self.open_music_folder, width=130, height=35, font=self.font_small, corner_radius=18, fg_color="#D4E8FF", hover_color="#B5D8FF", border_width=1, border_color="#B5D8FF", text_color=self.colors['text_dark']).pack(side="left", padx=(0, 8))
        ctk.CTkButton(button_row, text="✓ เลือกทั้งหมด", command=self.select_all_songs, width=110, height=35, font=self.font_small, corner_radius=18, fg_color=self.colors['secondary'], hover_color="#9EC8FF", border_width=1, border_color="#B5D8FF", text_color=self.colors['text_dark']).pack(side="left", padx=(0, 5))
        ctk.CTkButton(button_row, text="✗ ล้าง", command=self.clear_song_selection, width=70, height=35, font=self.font_small, corner_radius=18, fg_color="#F5F5F5", hover_color="#E8E8E8", border_width=1, border_color="#E0E0E0", text_color=self.colors['text_dark']).pack(side="left")
        
        self.song_frame = ctk.CTkFrame(song_card, fg_color="transparent")
        self.song_frame.pack(fill="x", padx=10, pady=(0, 15))
        self.rebuild_song_list()
        
        seek_card = self.create_hand_drawn_card("⏱️ ตำแหน่งเพลง", "คลิกและลากเพื่อเปลี่ยนตำแหน่ง")
        seek_slider_frame = ctk.CTkFrame(seek_card, fg_color="transparent")
        seek_slider_frame.pack(fill="x", padx=15, pady=(10, 5))
        
        self.seek_slider = ctk.CTkSlider(seek_slider_frame, from_=0, to=100, command=self.on_seek_change, height=20, button_length=25, button_color=self.colors['primary'], button_hover_color="#FF8A8A", progress_color=self.colors['primary'], fg_color="#F5F0EB", corner_radius=10)
        self.seek_slider.set(0)
        self.seek_slider.pack(side="left", fill="x", expand=True)
        
        self.seek_label = ctk.CTkLabel(seek_slider_frame, text="0:00 / 0:00", font=self.font_small, text_color="#B8B8B8", width=100)
        self.seek_label.pack(side="right", padx=(10, 0))
        
        mode_card = self.create_hand_drawn_card("🔄 โหมดการเล่น", "เลือกวิธีการเล่นเพลง")
        self.playback_mode_var = ctk.StringVar(value=self.playback_mode)
        mode_frame = ctk.CTkFrame(mode_card, fg_color="transparent")
        mode_frame.pack(fill="x", padx=15, pady=(5, 15))
        
        ctk.CTkRadioButton(mode_frame, text="🔁 เล่นซ้ำ (Loop)", variable=self.playback_mode_var, value="loop", font=self.font_normal, radiobutton_width=22, radiobutton_height=22, corner_radius=8, border_width_unchecked=2, border_width_checked=4, border_color=self.colors['primary'], fg_color=self.colors['primary'], hover_color=self.colors['accent'], text_color=self.colors['text_dark'], command=self.on_mode_change).pack(anchor="w", pady=5)
        ctk.CTkRadioButton(mode_frame, text="🔀 สุ่มเพลง (Shuffle)", variable=self.playback_mode_var, value="shuffle", font=self.font_normal, radiobutton_width=22, radiobutton_height=22, corner_radius=8, border_width_unchecked=2, border_width_checked=4, border_color=self.colors['primary'], fg_color=self.colors['primary'], hover_color=self.colors['accent'], text_color=self.colors['text_dark'], command=self.on_mode_change).pack(anchor="w", pady=5)
        
        volume_card = self.create_hand_drawn_card("🔊 ควบคุมเสียง", "ปรับระดับเสียงและความเร็วแบบเรียลไทม์")
        
        volume_header = ctk.CTkFrame(volume_card, fg_color="transparent")
        volume_header.pack(fill="x", padx=15, pady=(5, 0))
        ctk.CTkLabel(volume_header, text="ระดับเสียง:", font=self.font_normal, text_color=self.colors['text_dark']).pack(side="left")
        self.volume_label = ctk.CTkLabel(volume_header, text=f"{int(self.volume * 100)}%", font=self.font_normal, text_color=self.colors['primary'], width=60)
        self.volume_label.pack(side="right")
        
        volume_slider_frame = ctk.CTkFrame(volume_card, fg_color="transparent")
        volume_slider_frame.pack(fill="x", padx=15, pady=(5, 10))
        self.volume_slider = ctk.CTkSlider(volume_slider_frame, from_=0.0, to=1.0, command=self.on_volume_change, height=16, button_length=22, button_color=self.colors['primary'], button_hover_color="#FF8A8A", progress_color=self.colors['primary'], fg_color="#F5F0EB", corner_radius=8)
        self.volume_slider.set(self.volume)
        self.volume_slider.pack(side="left", fill="x", expand=True)
        
        speed_header = ctk.CTkFrame(volume_card, fg_color="transparent")
        speed_header.pack(fill="x", padx=15)
        ctk.CTkLabel(speed_header, text="ความเร็วเสียง:", font=self.font_normal, text_color=self.colors['text_dark']).pack(side="left")
        self.speed_label = ctk.CTkLabel(speed_header, text=f"x{self.playback_speed:.1f}", font=self.font_normal, text_color=self.colors['primary'], width=60)
        self.speed_label.pack(side="right")
        
        speed_slider_frame = ctk.CTkFrame(volume_card, fg_color="transparent")
        speed_slider_frame.pack(fill="x", padx=15, pady=(5, 10))
        self.speed_slider = ctk.CTkSlider(speed_slider_frame, from_=0.5, to=2.0, command=self.on_speed_change, height=16, button_length=22, button_color=self.colors['primary'], button_hover_color="#FF8A8A", progress_color=self.colors['primary'], fg_color="#F5F0EB", corner_radius=8)
        self.speed_slider.set(self.playback_speed)
        self.speed_slider.pack(side="left", fill="x", expand=True)
        
        save_frame = ctk.CTkFrame(volume_card, fg_color="transparent")
        save_frame.pack(fill="x", padx=15, pady=(0, 15))
        self.save_button = ctk.CTkButton(save_frame, text="💾 บันทึกการตั้งค่า", command=self.save_audio_settings, height=40, font=self.font_button, corner_radius=20, fg_color=self.colors['save'], hover_color="#FFC888", border_width=2, border_color="#FFD4A8", text_color=self.colors['text_dark'])
        self.save_button.pack(fill="x")
        
        control_card = self.create_hand_drawn_card("🎮 ควบคุมการเล่น", "")
        button_frame = ctk.CTkFrame(control_card, fg_color="transparent")
        button_frame.pack(fill="x", padx=15, pady=15)
        
        self.play_button = ctk.CTkButton(button_frame, text="▶️ เล่นเพลง", command=self.toggle_playback, width=140, height=50, font=self.font_button, corner_radius=25, fg_color=self.colors['success'], hover_color="#9ED89E", border_width=2, border_color="#A8D8A8", text_color=self.colors['text_dark'])
        self.play_button.pack(side="left", padx=(0, 8), expand=True)
        
        mute_text = "🔇 เปิดเสียง" if self.is_muted else "🔊 ปิดเสียง"
        self.mute_button = ctk.CTkButton(button_frame, text=mute_text, command=self.toggle_mute, width=140, height=50, font=self.font_button, corner_radius=25, fg_color=self.colors['accent'], hover_color="#FFD8A8", border_width=2, border_color="#FFE4B5", text_color=self.colors['text_dark'])
        self.mute_button.pack(side="left", padx=(0, 8), expand=True)
        
        ctk.CTkButton(button_frame, text="❌ ปิดโปรแกรม", command=self.exit_application, width=140, height=50, font=self.font_button, corner_radius=25, fg_color=self.colors['danger'], hover_color="#FF9E9E", border_width=2, border_color="#FFB5B5", text_color=self.colors['text_dark']).pack(side="left", expand=True)
        
        autostart_card = self.create_hand_drawn_card("🚀 เริ่มอัตโนมัติ", "ตั้งค่าเริ่มโปรแกรมกับ Windows")
        self.autostart_var = ctk.BooleanVar(value=self.is_autostart_enabled())
        ctk.CTkCheckBox(autostart_card, text="เริ่มอัตโนมัติตอนเปิดเครื่อง", variable=self.autostart_var, command=self.toggle_autostart, font=self.font_normal, checkbox_width=24, checkbox_height=24, corner_radius=10, border_width=2, border_color=self.colors['primary'], fg_color=self.colors['primary'], hover_color=self.colors['accent'], checkmark_color="white", text_color=self.colors['text_dark']).pack(anchor="w", padx=20, pady=20)
    
    def create_hand_drawn_card(self, title, subtitle=""):
        card = ctk.CTkFrame(self.scrollable_frame, fg_color="#FFFFFF", corner_radius=20, border_width=2, border_color=self.colors['border'])
        card.pack(fill="x", pady=(0, 12), padx=10)
        
        header_frame = ctk.CTkFrame(card, fg_color="transparent")
        header_frame.pack(fill="x", padx=15, pady=(12, 5))
        
        ctk.CTkLabel(header_frame, text=title, font=self.font_header, text_color=self.colors['text_dark']).pack(anchor="w")
        if subtitle:
            ctk.CTkLabel(header_frame, text=subtitle, font=self.font_small, text_color="#C8C8C8").pack(anchor="w", pady=(0, 5))
        
        return card
    
    def select_all_songs(self):
        if hasattr(self, 'song_vars'):
            for var in self.song_vars:
                var.set(True)
    
    def clear_song_selection(self):
        if hasattr(self, 'song_vars'):
            for var in self.song_vars:
                var.set(False)

    def apply_audio_changes(self):
        self.volume = self.temp_volume if self.temp_volume is not None else self.volume
        self.playback_speed = self.temp_speed if self.temp_speed is not None else self.playback_speed
        
        if self.is_playing:
            if self.song_duration > 0 and hasattr(self, 'current_play_time'):
                self.seek_position = (self.current_play_time / self.song_duration) * 100
            self.restart_current_song()
    
    def on_volume_change(self, value):
        self.temp_volume = float(value)
        self.volume_label.configure(text=f"{int(self.temp_volume * 100)}%")
        
        if self._vol_timer:
            self.root.after_cancel(self._vol_timer)
        self._vol_timer = self.root.after(400, self.apply_audio_changes)
    
    def on_speed_change(self, value):
        self.temp_speed = float(value)
        self.speed_label.configure(text=f"x{self.temp_speed:.1f}")
        
        if self._speed_timer:
            self.root.after_cancel(self._speed_timer)
        self._speed_timer = self.root.after(400, self.apply_audio_changes)
    
    def on_mode_change(self):
        self.temp_mode = self.playback_mode_var.get()
    
    def on_seek_change(self, value):
        self.seek_position = float(value)
        
        if self.song_duration > 0:
            current_time = int((self.seek_position / 100) * self.song_duration)
            current_min, current_sec = divmod(current_time, 60)
            total_min, total_sec = divmod(int(self.song_duration), 60)
            self.seek_label.configure(text=f"{current_min}:{current_sec:02d} / {total_min}:{total_sec:02d}")
        
        if self.is_playing:
            if self._seek_timer:
                self.root.after_cancel(self._seek_timer)
            self._seek_timer = self.root.after(400, self.restart_current_song)
    
    def restart_current_song(self):
        if not self.is_playing or not self.selected_files:
            return
        self.restart_flag.set()
    
    def get_selected_files(self):
        selected = []
        if hasattr(self, 'song_vars'):
            for i, var in enumerate(self.song_vars):
                if i < len(self.mp3_files) and var.get():
                    selected.append(self.mp3_files[i])
        return selected
    
    def toggle_playback(self):
        if self.is_playing:
            self.stop_playback()
        else:
            self.start_playback()
    
    def start_playback(self):
        if not self.ffmpeg_path:
            messagebox.showerror("ข้อผิดพลาด", "ไม่พบ FFmpeg กรุณาติดตั้ง FFmpeg ก่อนใช้งาน")
            return
        
        self.selected_files = self.get_selected_files()
        if not self.selected_files:
            messagebox.showwarning("แจ้งเตือน", "กรุณาเลือกเพลงอย่างน้อย 1 เพลง")
            return
        
        self.playback_mode = self.temp_mode if self.temp_mode else self.playback_mode
        self.playback_mode_var.set(self.playback_mode)
        self.current_file_index = 0
        
        if self.playback_mode == "shuffle":
            random.shuffle(self.selected_files)
        
        self.stop_event.clear()
        self.is_playing = True
        self.play_button.configure(text="⏸️ หยุดเล่น", fg_color="#FFE4B5", hover_color="#FFD8A8", border_color="#FFE4B5")
        self.status_label.configure(text="▶️ กำลังเล่นเพลง...", text_color="#8ED88E")
        
        self.play_thread = threading.Thread(target=self.play_music, daemon=True)
        self.play_thread.start()
    
    def stop_playback(self):
        self.stop_event.set()
        self.is_playing = False
        
        if self.current_process and self.current_process.poll() is None:
            try:
                self.current_process.terminate()
            except:
                pass
        
        if self.temp_wav_path and os.path.exists(self.temp_wav_path):
            try:
                os.remove(self.temp_wav_path)
            except:
                pass
            self.temp_wav_path = None
        
        self.play_button.configure(text="▶️ เล่นเพลง", fg_color=self.colors['success'], hover_color="#9ED89E", border_color="#A8D8A8")
        self.status_label.configure(text="⏸️ หยุดเล่นแล้ว", text_color="#C8C8C8")
    
    def play_music(self):
        try:
            while not self.stop_event.is_set() and self.is_playing and self.selected_files:
                current_file = self.selected_files[self.current_file_index]
                self.current_file = current_file
                filename = os.path.basename(current_file)
                
                self.root.after(0, lambda f=filename: self.status_label.configure(text=f"▶️ กำลังเล่น: {f[:30]}...", text_color="#8ED88E"))
                
                if not os.path.exists(current_file):
                    self.root.after(0, lambda f=filename: self.status_label.configure(text=f"❌ ไม่พบไฟล์: {f[:20]}", text_color="#E8A0A0"))
                    self.current_file_index = (self.current_file_index + 1) % len(self.selected_files)
                    continue
                
                self.song_duration = self.get_audio_duration(current_file)
                
                start_time = 0
                if self.seek_position > 0 and self.song_duration > 0:
                    start_time = (self.seek_position / 100) * self.song_duration
                
                self.current_play_time = start_time
                
                with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_wav:
                    self.temp_wav_path = temp_wav.name
                
                try:
                    current_volume = 0 if self.is_muted else self.volume
                    current_speed = self.playback_speed
                    
                    volume_filter = f"volume={current_volume}"
                    speed_filter = f"atempo={current_speed}"
                    filter_complex = f"{volume_filter},{speed_filter}"
                    
                    cmd = [
                        self.ffmpeg_path,
                        '-ss', str(start_time),
                        '-i', current_file,
                        '-af', filter_complex,
                        '-acodec', 'pcm_s16le',
                        '-ar', '44100',
                        '-ac', '2',
                        self.temp_wav_path,
                        '-y'
                    ]
                    
                    # ซ่อนหน้าต่างและระบาย Output ทิ้งเพื่อลดการกินทรัพยากร
                    subprocess.run(
                        cmd, 
                        check=True, 
                        timeout=30, 
                        creationflags=CREATE_NO_WINDOW,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                    
                    ps_cmd = ['powershell', '-c', f"(New-Object Media.SoundPlayer '{self.temp_wav_path}').PlaySync()"]
                    
                    # ซ่อนหน้าต่าง PowerShell อย่างสมบูรณ์
                    self.current_process = subprocess.Popen(
                        ps_cmd,
                        creationflags=CREATE_NO_WINDOW,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                    
                    start_play_time = time.time()
                    should_restart = False
                    
                    while self.current_process.poll() is None:
                        if self.stop_event.is_set() or not self.is_playing:
                            self.current_process.terminate()
                            break
                        if self.restart_flag.is_set():
                            self.current_process.terminate()
                            self.restart_flag.clear()
                            should_restart = True
                            break
                        
                        if self.song_duration > 0:
                            elapsed_real = time.time() - start_play_time
                            self.current_play_time = start_time + (elapsed_real * current_speed)
                            
                            if self.current_play_time > self.song_duration:
                                self.current_play_time = self.song_duration
                                
                            progress = (self.current_play_time / self.song_duration) * 100
                            current_min, current_sec = divmod(int(self.current_play_time), 60)
                            total_min, total_sec = divmod(int(self.song_duration), 60)
                            
                            self.root.after(0, lambda p=progress, cm=current_min, cs=current_sec, tm=total_min, ts=total_sec: self.update_seek_ui(p, cm, cs, tm, ts))
                        
                        time.sleep(0.3)
                    
                    try:
                        self.current_process.wait(timeout=1)
                    except:
                        pass
                    
                    if should_restart:
                        continue
                        
                except subprocess.TimeoutExpired:
                    pass
                except Exception as e:
                    error_msg = str(e)[:30]
                    self.root.after(0, lambda msg=error_msg: self.status_label.configure(text=f"❌ เกิดข้อผิดพลาด: {msg}", text_color="#E8A0A0"))
                finally:
                    if self.temp_wav_path and os.path.exists(self.temp_wav_path):
                        try:
                            os.remove(self.temp_wav_path)
                        except:
                            pass
                        self.temp_wav_path = None
                
                self.seek_position = 0
                self.current_play_time = 0
                self.root.after(0, lambda: self.seek_slider.set(0))
                
                if self.playback_mode == "loop":
                    self.current_file_index = (self.current_file_index + 1) % len(self.selected_files)
                elif self.playback_mode == "shuffle":
                    if len(self.selected_files) > 1:
                        random.shuffle(self.selected_files)
                    self.current_file_index = 0
                
                if self.stop_event.is_set() or not self.is_playing:
                    break
                    
        except Exception as e:
            error_msg = str(e)[:30]
            self.root.after(0, lambda msg=error_msg: self.status_label.configure(text=f"❌ เกิดข้อผิดพลาด: {msg}", text_color="#E8A0A0"))
        finally:
            if self.temp_wav_path and os.path.exists(self.temp_wav_path):
                try:
                    os.remove(self.temp_wav_path)
                except:
                    pass
                self.temp_wav_path = None
            self.root.after(0, self.stop_playback)
    
    def update_seek_ui(self, progress, current_min, current_sec, total_min, total_sec):
        self.seek_slider.set(progress)
        self.seek_label.configure(text=f"{current_min}:{current_sec:02d} / {total_min}:{total_sec:02d}")
    
    def toggle_mute(self):
        self.is_muted = not self.is_muted
        
        if self.is_muted:
            self.mute_button.configure(text="🔇 เปิดเสียง", fg_color="#E8E8E8", hover_color="#D8D8D8", border_color="#D0D0D0")
            if self.is_playing:
                self.status_label.configure(text="🔇 ปิดเสียง", text_color="#E8A0A0")
        else:
            self.mute_button.configure(text="🔊 ปิดเสียง", fg_color=self.colors['accent'], hover_color="#FFD8A8", border_color="#FFE4B5")
            if self.is_playing:
                self.status_label.configure(text="▶️ กำลังเล่นเพลง...", text_color="#8ED88E")
        
        if self.is_playing:
            if self.song_duration > 0 and hasattr(self, 'current_play_time'):
                self.seek_position = (self.current_play_time / self.song_duration) * 100
            self.restart_current_song()
    
    def toggle_autostart(self):
        if self.autostart_var.get():
            self.enable_autostart()
        else:
            self.disable_autostart()
    
    def is_autostart_enabled(self):
        try:
            reg_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            reg_key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, reg_path)
            try:
                winreg.QueryValueEx(reg_key, "BGMPlayer")
                return True
            except WindowsError:
                return False
            finally:
                winreg.CloseKey(reg_key)
        except Exception:
            return False
    
    def enable_autostart(self):
        try:
            if getattr(sys, 'frozen', False):
                exe_path = sys.executable
            else:
                script_path = os.path.abspath(__file__)
                exe_path = f'"{sys.executable}" "{script_path}"'
            
            reg_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            reg_key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, reg_path, 0, winreg.KEY_SET_VALUE)
            winreg.SetValueEx(reg_key, "BGMPlayer", 0, winreg.REG_SZ, exe_path)
            winreg.CloseKey(reg_key)
            messagebox.showinfo("สำเร็จ", "เปิดใช้งานเริ่มอัตโนมัติแล้ว")
        except Exception as e:
            messagebox.showerror("ข้อผิดพลาด", f"ไม่สามารถตั้งค่าเริ่มอัตโนมัติ: {e}")
    
    def disable_autostart(self):
        try:
            reg_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            reg_key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, reg_path, 0, winreg.KEY_SET_VALUE)
            try:
                winreg.DeleteValue(reg_key, "BGMPlayer")
            except WindowsError:
                pass
            winreg.CloseKey(reg_key)
            messagebox.showinfo("สำเร็จ", "ปิดใช้งานเริ่มอัตโนมัติแล้ว")
        except Exception as e:
            messagebox.showerror("ข้อผิดพลาด", f"ไม่สามารถปิดใช้งานเริ่มอัตโนมัติ: {e}")
    
    def exit_application(self, icon=None, item=None):
        self.on_closing()
    
    def on_closing(self):
        try:
            self.save_audio_settings()
            self.stop_event.set()
            self.is_playing = False
            
            if self.current_process and self.current_process.poll() is None:
                try:
                    self.current_process.terminate()
                    self.current_process.wait(timeout=2)
                except:
                    try:
                        self.current_process.kill()
                    except:
                        pass
            
            if self.temp_wav_path and os.path.exists(self.temp_wav_path):
                try:
                    os.remove(self.temp_wav_path)
                except:
                    pass
                self.temp_wav_path = None
            
            if self.tray_icon:
                self.tray_icon.stop()
            
            try:
                # ซ่อนหน้าต่างตอนเคลียร์ process สุดท้ายด้วย
                subprocess.run(
                    ['taskkill', '/F', '/IM', 'powershell.exe'], 
                    creationflags=CREATE_NO_WINDOW,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=2
                )
            except:
                pass
                
        except Exception:
            pass
        
        self.root.destroy()
        sys.exit(0)

def main():
    root = ctk.CTk()
    app = BGMPlayer(root)
    root.mainloop()

if __name__ == "__main__":
    main()