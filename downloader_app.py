import json
import os
import re
import subprocess
import threading
from pathlib import Path
import customtkinter as ctk


APP_DIR = Path(__file__).resolve().parent
CONFIG_FILE = APP_DIR / "config.json"

# Строгий чёрно-белый палитр-сет
BW_BG_MAIN = "#0B0B0B"
BW_BG_CARD = "#141414"
BW_BG_INPUT = "#1C1C1C"
BW_BORDER = "#2E2E2E"
BW_TEXT_MAIN = "#F5F5F5"
BW_TEXT_MUTED = "#9A9A9A"
BW_BTN_PRIMARY = "#FFFFFF"
BW_BTN_PRIMARY_TEXT = "#0B0B0B"
BW_BTN_PRIMARY_HOVER = "#DCDCDC"
BW_BTN_SECONDARY = "#1E1E1E"
BW_BTN_SECONDARY_HOVER = "#2A2A2A"
BW_PROGRESS = "#FFFFFF"

PCT_RE = re.compile(r"\[download\]\s+(\d+(?:\.\d+)?)%")
INVALID_CHARS_RE = re.compile(r'[\\/:*?"<>|]+')


def find_binary(name: str) -> str:
    exe_path = APP_DIR / f"{name}.exe"
    if exe_path.is_file():
        return str(exe_path)
    plain_path = APP_DIR / name
    if plain_path.is_file():
        return str(plain_path)
    return name


def sanitize_filename(raw_name: str) -> str:
    cleaned = INVALID_CHARS_RE.sub("_", raw_name).strip(" .")
    return cleaned


class YtDlpApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("yt-dlp // monochrome")
        self.geometry("760x660")
        self.minsize(680, 600)
        ctk.set_appearance_mode("dark")
        self.configure(fg_color=BW_BG_MAIN)

        self.is_running = False
        self.config_data = self._load_config()
        self._build_ui()
        self._check_binaries()

    def _load_config(self) -> dict:
        defaults = {
            "out_dir": str(APP_DIR),
            "quality": "Максимум",
            "cookies": "Без cookies",
            "no_audio": False,
            "proxy": "",
        }
        if CONFIG_FILE.is_file():
            try:
                loaded = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    defaults.update(loaded)
            except Exception:
                pass
        return defaults

    def _save_config(self):
        data = {
            "out_dir": self.out_dir_var.get().strip() or str(APP_DIR),
            "quality": self.quality_var.get(),
            "cookies": self.cookies_var.get(),
            "no_audio": bool(self.no_audio_var.get()),
            "proxy": self.proxy_entry.get().strip(),
        }
        try:
            CONFIG_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    def _build_ui(self):
        # Верхняя панель с названием и кнопкой открытия папки
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=18, pady=(16, 8))

        ctk.CTkLabel(
            header,
            text="YT-DLP DOWNLOADER (ЗАГРУЗЧИК МЕДИА)",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=BW_TEXT_MAIN,
        ).pack(side="left")

        self.open_folder_btn = ctk.CTkButton(
            header,
            text="Открыть папку",
            width=130,
            height=32,
            fg_color=BW_BTN_SECONDARY,
            hover_color=BW_BTN_SECONDARY_HOVER,
            text_color=BW_TEXT_MAIN,
            border_width=1,
            border_color=BW_BORDER,
            command=self.open_output_folder,
        )
        self.open_folder_btn.pack(side="right")

        # Карточка ввода ссылки и имени файла
        card_input = ctk.CTkFrame(
            self,
            fg_color=BW_BG_CARD,
            border_width=1,
            border_color=BW_BORDER,
            corner_radius=10,
        )
        card_input.pack(fill="x", padx=18, pady=6)

        ctk.CTkLabel(
            card_input,
            text="Ссылка на YouTube",
            font=ctk.CTkFont(size=12),
            text_color=BW_TEXT_MUTED,
        ).pack(anchor="w", padx=14, pady=(12, 4))

        self.url_entry = ctk.CTkEntry(
            card_input,
            height=36,
            placeholder_text="https://www.youtube.com/watch?v=...",
            fg_color=BW_BG_INPUT,
            border_color=BW_BORDER,
            text_color=BW_TEXT_MAIN,
            placeholder_text_color=BW_TEXT_MUTED,
        )
        self.url_entry.pack(fill="x", padx=14, pady=(0, 10))

        ctk.CTkLabel(
            card_input,
            text="Своё имя файла (необязательно — если пусто, возьмётся название ролика)",
            font=ctk.CTkFont(size=12),
            text_color=BW_TEXT_MUTED,
        ).pack(anchor="w", padx=14, pady=(0, 4))

        self.custom_name_entry = ctk.CTkEntry(
            card_input,
            height=34,
            placeholder_text="Например: bmw_m5_edit (расширение добавится автоматически)",
            fg_color=BW_BG_INPUT,
            border_color=BW_BORDER,
            text_color=BW_TEXT_MAIN,
            placeholder_text_color=BW_TEXT_MUTED,
        )
        self.custom_name_entry.pack(fill="x", padx=14, pady=(0, 14))

        # Карточка параметров
        card_opts = ctk.CTkFrame(
            self,
            fg_color=BW_BG_CARD,
            border_width=1,
            border_color=BW_BORDER,
            corner_radius=10,
        )
        card_opts.pack(fill="x", padx=18, pady=6)

        row_opts = ctk.CTkFrame(card_opts, fg_color="transparent")
        row_opts.pack(fill="x", padx=14, pady=(12, 8))

        ctk.CTkLabel(row_opts, text="Качество:", text_color=BW_TEXT_MUTED).pack(side="left", padx=(0, 8))
        self.quality_var = ctk.StringVar(value=self.config_data["quality"])
        self.quality_menu = ctk.CTkOptionMenu(
            row_opts,
            values=["Максимум", "1080p", "720p", "Только MP3"],
            variable=self.quality_var,
            command=self._on_quality_change,
            width=145,
            fg_color=BW_BG_INPUT,
            button_color=BW_BTN_SECONDARY,
            button_hover_color=BW_BTN_SECONDARY_HOVER,
            dropdown_fg_color=BW_BG_CARD,
            dropdown_hover_color=BW_BG_INPUT,
            text_color=BW_TEXT_MAIN,
            dropdown_text_color=BW_TEXT_MAIN,
        )
        self.quality_menu.pack(side="left", padx=(0, 18))

        ctk.CTkLabel(row_opts, text="Cookies:", text_color=BW_TEXT_MUTED).pack(side="left", padx=(0, 8))
        cookie_options = ["Без cookies", "cookies.txt (из папки)", "chrome", "edge", "firefox", "brave"]
        saved_cookie = self.config_data["cookies"]
        self.cookies_var = ctk.StringVar(value=saved_cookie if saved_cookie in cookie_options else "Без cookies")
        self.cookies_menu = ctk.CTkOptionMenu(
            row_opts,
            values=cookie_options,
            variable=self.cookies_var,
            width=185,
            fg_color=BW_BG_INPUT,
            button_color=BW_BTN_SECONDARY,
            button_hover_color=BW_BTN_SECONDARY_HOVER,
            dropdown_fg_color=BW_BG_CARD,
            dropdown_hover_color=BW_BG_INPUT,
            text_color=BW_TEXT_MAIN,
            dropdown_text_color=BW_TEXT_MAIN,
        )
        self.cookies_menu.pack(side="left")

        # Необязательный прокси (--proxy)
        row_proxy = ctk.CTkFrame(card_opts, fg_color="transparent")
        row_proxy.pack(fill="x", padx=14, pady=(0, 8))

        ctk.CTkLabel(row_proxy, text="Прокси (--proxy):", text_color=BW_TEXT_MUTED).pack(side="left", padx=(0, 8))
        self.proxy_entry = ctk.CTkEntry(
            row_proxy,
            height=32,
            placeholder_text="Необязательно: socks5://127.0.0.1:1080 или http://user:pass@host:port",
            fg_color=BW_BG_INPUT,
            border_color=BW_BORDER,
            text_color=BW_TEXT_MAIN,
            placeholder_text_color=BW_TEXT_MUTED,
        )
        self.proxy_entry.pack(side="left", fill="x", expand=True)
        if self.config_data.get("proxy"):
            self.proxy_entry.insert(0, self.config_data["proxy"])

        self.no_audio_var = ctk.BooleanVar(value=self.config_data["no_audio"])
        self.no_audio_chk = ctk.CTkCheckBox(
            card_opts,
            text="Только видеопоток без звука (игнорируется для MP3)",
            variable=self.no_audio_var,
            fg_color=BW_BTN_PRIMARY,
            hover_color=BW_BTN_PRIMARY_HOVER,
            checkmark_color=BW_BTN_PRIMARY_TEXT,
            border_color=BW_TEXT_MUTED,
            text_color=BW_TEXT_MAIN,
        )
        self.no_audio_chk.pack(anchor="w", padx=14, pady=(2, 10))
        self._on_quality_change(self.quality_var.get())

        row_dir = ctk.CTkFrame(card_opts, fg_color="transparent")
        row_dir.pack(fill="x", padx=14, pady=(0, 14))

        self.out_dir_var = ctk.StringVar(value=self.config_data["out_dir"])
        self.out_entry = ctk.CTkEntry(
            row_dir,
            height=36,
            textvariable=self.out_dir_var,
            fg_color=BW_BG_INPUT,
            border_color=BW_BORDER,
            text_color=BW_TEXT_MAIN,
        )
        self.out_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.download_btn = ctk.CTkButton(
            row_dir,
            text="Скачать",
            width=135,
            height=36,
            font=ctk.CTkFont(weight="bold"),
            fg_color=BW_BTN_PRIMARY,
            hover_color=BW_BTN_PRIMARY_HOVER,
            text_color=BW_BTN_PRIMARY_TEXT,
            command=self.start_download,
        )
        self.download_btn.pack(side="right")

        # Прогресс-бар
        progress_wrap = ctk.CTkFrame(self, fg_color="transparent")
        progress_wrap.pack(fill="x", padx=18, pady=(8, 4))

        self.progress_label = ctk.CTkLabel(
            progress_wrap,
            text="Ожидание — 0%",
            font=ctk.CTkFont(size=12),
            text_color=BW_TEXT_MUTED,
        )
        self.progress_label.pack(anchor="w", pady=(0, 4))

        self.progress_bar = ctk.CTkProgressBar(
            progress_wrap,
            height=10,
            corner_radius=5,
            fg_color=BW_BG_INPUT,
            progress_color=BW_PROGRESS,
        )
        self.progress_bar.pack(fill="x")
        self.progress_bar.set(0)

        # Лог
        ctk.CTkLabel(
            self,
            text="Лог выполнения",
            font=ctk.CTkFont(size=12),
            text_color=BW_TEXT_MUTED,
        ).pack(anchor="w", padx=18, pady=(8, 4))

        self.log_box = ctk.CTkTextbox(
            self,
            state="disabled",
            wrap="word",
            fg_color=BW_BG_CARD,
            border_width=1,
            border_color=BW_BORDER,
            text_color=BW_TEXT_MAIN,
            font=ctk.CTkFont(family="Consolas", size=12),
        )
        self.log_box.pack(fill="both", expand=True, padx=18, pady=(0, 18))

    def _check_binaries(self):
        self._append_log(f"yt-dlp : {find_binary('yt-dlp')}\n")
        self._append_log(f"ffmpeg : {find_binary('ffmpeg')}\n")
        if (APP_DIR / "cookies.txt").is_file():
            self._append_log(f"cookies: {APP_DIR / 'cookies.txt'}\n")

    def _on_quality_change(self, value: str):
        self.no_audio_chk.configure(state="disabled" if value == "Только MP3" else "normal")

    def _append_log(self, text: str):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", text)
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _set_progress(self, pct: float, status_text: str | None = None):
        clamped = max(0.0, min(100.0, pct))
        self.progress_bar.set(clamped / 100.0)
        if status_text:
            self.progress_label.configure(text=status_text)
        else:
            self.progress_label.configure(text=f"Загрузка — {clamped:.1f}%")

    def open_output_folder(self):
        target = Path(self.out_dir_var.get().strip() or str(APP_DIR))
        target.mkdir(parents=True, exist_ok=True)
        try:
            os.startfile(str(target))
        except Exception as exc:
            self._append_log(f"[ERR] Не удалось открыть папку: {exc}\n")

    def _build_output_template(self, out_dir: Path, is_audio: bool, custom_name: str) -> str:
        if custom_name:
            stem = Path(custom_name).stem or custom_name
            return str(out_dir / f"{stem}.%(ext)s")
        if is_audio:
            return str(out_dir / "%(title)s.%(ext)s")
        return str(out_dir / "%(title)s [%(resolution)s].%(ext)s")

    def _build_command(self, url: str, out_dir: Path, custom_name: str, proxy: str) -> list[str]:
        ytdlp_bin = find_binary("yt-dlp")
        ffmpeg_bin = find_binary("ffmpeg")

        cmd = [ytdlp_bin, "--newline", "--no-colors"]

        if Path(ffmpeg_bin).is_file():
            cmd.extend(["--ffmpeg-location", str(Path(ffmpeg_bin).parent)])

        if proxy:
            cmd.extend(["--proxy", proxy])

        cookie_mode = self.cookies_var.get()
        if cookie_mode == "cookies.txt (из папки)":
            cookies_file = APP_DIR / "cookies.txt"
            if cookies_file.is_file():
                cmd.extend(["--cookies", str(cookies_file)])
            else:
                self._append_log("[!] cookies.txt не найден рядом со скриптом, запускаю без cookies.\n")
        elif cookie_mode != "Без cookies":
            cmd.extend(["--cookies-from-browser", cookie_mode])

        quality = self.quality_var.get()
        if quality == "Только MP3":
            out_tpl = self._build_output_template(out_dir, is_audio=True, custom_name=custom_name)
            cmd.extend([
                "-x",
                "--audio-format", "mp3",
                "--audio-quality", "0",
                "-o", out_tpl,
            ])
        else:
            out_tpl = self._build_output_template(out_dir, is_audio=False, custom_name=custom_name)
            height_filter = ""
            if quality == "1080p":
                height_filter = "[height<=1080]"
            elif quality == "720p":
                height_filter = "[height<=720]"

            if self.no_audio_var.get():
                fmt = f"bv*{height_filter}/b{height_filter}"
            else:
                fmt = f"bv*{height_filter}+ba/b{height_filter}"
                cmd.extend(["--merge-output-format", "mp4"])

            cmd.extend([
                "-f", fmt,
                "-o", out_tpl,
            ])

        cmd.append(url)
        return cmd

    def start_download(self):
        if self.is_running:
            return

        url = self.url_entry.get().strip()
        if not url:
            self._append_log("[!] Введи ссылку на видео.\n")
            return

        raw_custom = self.custom_name_entry.get().strip()
        custom_name = sanitize_filename(raw_custom) if raw_custom else ""
        if raw_custom and not custom_name:
            self._append_log("[!] Имя файла состоит только из недопустимых символов.\n")
            return

        proxy = self.proxy_entry.get().strip()
        out_dir = Path(self.out_dir_var.get().strip() or str(APP_DIR))
        out_dir.mkdir(parents=True, exist_ok=True)
        self._save_config()

        cmd = self._build_command(url, out_dir, custom_name, proxy)
        self.is_running = True
        self.download_btn.configure(state="disabled", text="Загрузка...")
        self._set_progress(0, "Запуск — 0%")
        self._append_log(f"\n--- Запуск: {' '.join(cmd)} ---\n")

        threading.Thread(target=self._run_process, args=(cmd,), daemon=True).start()

    def _run_process(self, cmd: list[str]):
        creationflags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=creationflags,
            )
            assert process.stdout is not None
            for line in process.stdout:
                self.after(0, self._append_log, line)
                match = PCT_RE.search(line)
                if match:
                    pct = float(match.group(1))
                    self.after(0, self._set_progress, pct, None)
                elif line.startswith("[Merger]") or line.startswith("[ExtractAudio]"):
                    self.after(0, self._set_progress, 99.0, "Обработка / склейка — 99%")

            code = process.wait()
            if code == 0:
                self.after(0, self._set_progress, 100.0, "Готово — 100%")
                self.after(0, self._append_log, "\n[OK] Готово!\n")
            else:
                self.after(0, self._set_progress, 0.0, f"Ошибка (код {code})")
                self.after(0, self._append_log, f"\n[ERR] Завершено с кодом {code}\n")
        except FileNotFoundError:
            self.after(0, self._set_progress, 0.0, "Ошибка — не найден yt-dlp")
            self.after(0, self._append_log, "\n[ERR] Не найден yt-dlp.exe ни рядом со скриптом, ни в PATH.\n")
        except Exception as exc:
            self.after(0, self._set_progress, 0.0, "Ошибка выполнения")
            self.after(0, self._append_log, f"\n[ERR] {exc}\n")
        finally:
            self.after(0, self._reset_state)

    def _reset_state(self):
        self.is_running = False
        self.download_btn.configure(state="normal", text="Скачать")


if __name__ == "__main__":
    app = YtDlpApp()
    app.mainloop()