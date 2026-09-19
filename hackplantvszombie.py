import os
import socket
import subprocess
import threading
import time
import urllib.parse
import http.server
import socketserver
import customtkinter as ctk
import psutil
import ctypes
from ctypes import wintypes

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("green")

PROCESS_ALL_ACCESS = 0x1F0FFF
PAGE_EXECUTE_READWRITE = 0x40

def enable_debug_privilege():
    try:
        import win32api, win32security
        hToken = win32security.OpenProcessToken(
            win32api.GetCurrentProcess(),
            win32security.TOKEN_ADJUST_PRIVILEGES | win32security.TOKEN_QUERY
        )
        luid = win32security.LookupPrivilegeValue(None, win32security.SE_DEBUG_NAME)
        win32security.AdjustTokenPrivileges(
            hToken, False, [(luid, win32security.SE_PRIVILEGE_ENABLED)]
        )
    except Exception:
        pass

enable_debug_privilege()

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

class MemoryEngine:
    @staticmethod
    def read_memory(pid, addr_hex, val_type):
        if not pid or pid <= 0:
            return "N/A"
        try:
            target_addr = int(addr_hex, 16)
        except ValueError:
            return "N/A"

        process_handle = ctypes.windll.kernel32.OpenProcess(PROCESS_ALL_ACCESS, False, pid)
        if not process_handle:
            return "N/A"

        if "Float" in val_type:
            buffer = ctypes.c_float()
        elif "Double" in val_type:
            buffer = ctypes.c_double()
        elif "Int64" in val_type or "8 Bytes" in val_type:
            buffer = ctypes.c_int64()
        elif "2 Bytes" in val_type:
            buffer = ctypes.c_int16()
        elif "1 Byte" in val_type:
            buffer = ctypes.c_uint8()
        else:
            buffer = ctypes.c_int32()

        size = ctypes.sizeof(buffer)
        old_protect = wintypes.DWORD()

        ctypes.windll.kernel32.VirtualProtectEx(
            process_handle, ctypes.c_void_p(target_addr), ctypes.c_size_t(size),
            PAGE_EXECUTE_READWRITE, ctypes.byref(old_protect)
        )

        bytes_read = ctypes.c_size_t()
        success = ctypes.windll.kernel32.ReadProcessMemory(
            process_handle, ctypes.c_void_p(target_addr), ctypes.byref(buffer),
            size, ctypes.byref(bytes_read)
        )

        ctypes.windll.kernel32.VirtualProtectEx(
            process_handle, ctypes.c_void_p(target_addr), ctypes.c_size_t(size),
            old_protect, ctypes.byref(old_protect)
        )
        ctypes.windll.kernel32.CloseHandle(process_handle)

        if success and bytes_read.value == size:
            val = buffer.value
            if isinstance(val, float):
                return str(round(val, 3))
            return str(val)
        return "N/A"

    @staticmethod
    def write_memory(pid, addr_hex, val_str, val_type):
        if not pid or pid <= 0:
            return False
        try:
            target_addr = int(addr_hex, 16)
        except ValueError:
            return False

        process_handle = ctypes.windll.kernel32.OpenProcess(PROCESS_ALL_ACCESS, False, pid)
        if not process_handle:
            return False

        try:
            if "Float" in val_type:
                buffer = ctypes.c_float(float(val_str))
            elif "Double" in val_type:
                buffer = ctypes.c_double(float(val_str))
            elif "Int64" in val_type or "8 Bytes" in val_type:
                buffer = ctypes.c_int64(int(val_str))
            elif "2 Bytes" in val_type:
                buffer = ctypes.c_int16(int(val_str))
            elif "1 Byte" in val_type:
                buffer = ctypes.c_uint8(int(val_str))
            else:
                buffer = ctypes.c_int32(int(val_str))
        except ValueError:
            ctypes.windll.kernel32.CloseHandle(process_handle)
            return False

        size = ctypes.sizeof(buffer)
        old_protect = wintypes.DWORD()

        ctypes.windll.kernel32.VirtualProtectEx(
            process_handle, ctypes.c_void_p(target_addr), ctypes.c_size_t(size),
            PAGE_EXECUTE_READWRITE, ctypes.byref(old_protect)
        )

        bytes_written = ctypes.c_size_t()
        success = ctypes.windll.kernel32.WriteProcessMemory(
            process_handle, ctypes.c_void_p(target_addr), ctypes.byref(buffer),
            size, ctypes.byref(bytes_written)
        )

        ctypes.windll.kernel32.VirtualProtectEx(
            process_handle, ctypes.c_void_p(target_addr), ctypes.c_size_t(size),
            old_protect, ctypes.byref(old_protect)
        )
        ctypes.windll.kernel32.CloseHandle(process_handle)

        return success and bytes_written.value == size

# WEB REMOTE TRÊN ĐIỆN THOẠI
HTML_PHONE_PAGE = """<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
    <title>RAM Remote Control</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-950 text-slate-100 min-h-screen flex items-center justify-center p-4">
    <div class="w-full max-w-sm bg-slate-900 border-2 border-emerald-500 rounded-2xl p-6 shadow-2xl">
        <h2 class="text-xl font-bold text-emerald-400 text-center mb-1">⚡ RAM REMOTE</h2>
        <p class="text-xs text-slate-400 text-center mb-5">Địa chỉ RAM dùng đồng bộ từ PC</p>
        
        <div class="bg-slate-800/90 border border-slate-700 rounded-xl p-4 mb-5 text-center">
            <span class="text-xs text-slate-400 block mb-1">Giá trị hiện tại trong RAM:</span>
            <div id="liveVal" class="text-4xl font-extrabold text-emerald-400 my-1">---</div>
        </div>

        <div class="mb-4">
            <label class="block text-xs font-semibold text-slate-300 mb-1">Nhập giá trị mới gửi lên PC:</label>
            <input type="number" id="valInput" value="999" class="w-full bg-slate-800 border border-slate-700 rounded-xl p-3 text-center text-lg text-emerald-400 font-bold focus:outline-none focus:border-emerald-500">
        </div>

        <button onclick="writeVal()" class="w-full bg-emerald-600 hover:bg-emerald-500 text-white font-bold py-3 text-base rounded-xl mb-3 active:scale-95 transition shadow-lg">
            💉 INJECT VALUE
        </button>

        <button id="freezeBtn" onclick="toggleFreeze()" class="w-full bg-sky-600 hover:bg-sky-500 text-white font-bold py-3 text-base rounded-xl mb-4 active:scale-95 transition shadow-lg">
            ❄ FREEZE
        </button>
        
        <div id="status" class="text-center text-xs text-emerald-400 font-semibold">● Đã kết nối PC</div>
    </div>

    <script>
        let isFrozen = false;

        function fetchValue() {
            fetch('/read')
            .then(r => r.json())
            .then(data => { 
                document.getElementById('liveVal').innerText = data.val;
                let btn = document.getElementById('freezeBtn');
                if (data.is_frozen !== isFrozen) {
                    isFrozen = data.is_frozen;
                    if (isFrozen) {
                        btn.innerText = "🔥 UNFREEZE";
                        btn.className = "w-full bg-red-600 hover:bg-red-500 text-white font-bold py-3 text-base rounded-xl mb-4 active:scale-95 transition shadow-lg";
                    } else {
                        btn.innerText = "❄ FREEZE";
                        btn.className = "w-full bg-sky-600 hover:bg-sky-500 text-white font-bold py-3 text-base rounded-xl mb-4 active:scale-95 transition shadow-lg";
                    }
                }
            })
            .catch(() => { 
                document.getElementById('liveVal').innerText = "N/A"; 
                document.getElementById('status').innerText = "❌ Mất kết nối PC";
            });
        }

        setInterval(fetchValue, 500);

        function writeVal() {
            let val = document.getElementById('valInput').value;
            fetch('/write?val=' + encodeURIComponent(val))
            .then(r => r.text())
            .then(msg => {
                document.getElementById('status').innerText = msg;
                fetchValue();
            });
        }

        function toggleFreeze() {
            let val = document.getElementById('valInput').value;
            fetch('/toggle_freeze?val=' + encodeURIComponent(val))
            .then(r => r.text())
            .then(msg => { 
                document.getElementById('status').innerText = msg;
                fetchValue();
            });
        }
    </script>
</body>
</html>"""

class PhoneServerHandler(http.server.BaseHTTPRequestHandler):
    trainer_app = None

    def log_message(self, format, *args):
        return

    def do_GET(self):
        import json
        try:
            parsed = urllib.parse.urlparse(self.path)

            if parsed.path == '/':
                self.send_response(200)
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.end_headers()
                self.wfile.write(HTML_PHONE_PAGE.encode('utf-8'))

            elif parsed.path == '/read':
                val_text = "N/A"
                is_frozen = False

                if PhoneServerHandler.trainer_app:
                    val_text = PhoneServerHandler.trainer_app.read_valuable_safe()
                    is_frozen = PhoneServerHandler.trainer_app.is_frozen

                response_data = {"val": val_text, "is_frozen": is_frozen}
                self.send_response(200)
                self.send_header('Content-type', 'application/json; charset=utf-8')
                self.end_headers()
                self.wfile.write(json.dumps(response_data).encode('utf-8'))

            elif parsed.path == '/write':
                query = urllib.parse.parse_qs(parsed.query)
                new_val = query.get('val', ['999'])[0]
                msg = "❌ Lỗi ghi dữ liệu"

                if PhoneServerHandler.trainer_app:
                    PhoneServerHandler.trainer_app.set_value_from_phone(new_val)
                    msg = f"✔ Đã Inject {new_val} từ ĐT!"

                self.send_response(200)
                self.send_header('Content-type', 'text/plain; charset=utf-8')
                self.end_headers()
                self.wfile.write(msg.encode('utf-8'))

            elif parsed.path == '/toggle_freeze':
                query = urllib.parse.parse_qs(parsed.query)
                new_val = query.get('val', ['999'])[0]
                msg = "❌ App chưa sẵn sàng"

                if PhoneServerHandler.trainer_app:
                    PhoneServerHandler.trainer_app.set_value_from_phone(new_val)
                    PhoneServerHandler.trainer_app.toggle_freeze_safe()
                    if PhoneServerHandler.trainer_app.is_frozen:
                        msg = "❄ Đã BẬT Đóng Băng!"
                    else:
                        msg = "🔥 Đã TẮT Đóng Băng!"

                self.send_response(200)
                self.send_header('Content-type', 'text/plain; charset=utf-8')
                self.end_headers()
                self.wfile.write(msg.encode('utf-8'))
            else:
                self.send_error(404)
        except Exception:
            pass

class ThreadedHTTPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    daemon_threads = True
    allow_reuse_address = True

class ProcessPickerWindow(ctk.CTkToplevel):
    def __init__(self, parent, on_select_callback):
        super().__init__(parent)
        self.title("Chọn ứng dụng / Process")
        self.geometry("460x520")
        self.resizable(False, False)
        self.on_select_callback = on_select_callback
        self.attributes("-topmost", True)

        self.all_processes = []

        self.label = ctk.CTkLabel(self, text="Danh sách ứng dụng đang chạy:", font=ctk.CTkFont(size=14, weight="bold"))
        self.label.pack(pady=(10, 5))

        self.search_entry = ctk.CTkEntry(self, placeholder_text="🔍 Nhập tên App hoặc Mã PID Hex...", width=420)
        self.search_entry.pack(pady=5, padx=10)
        self.search_entry.bind("<KeyRelease>", self.filter_processes)

        self.scroll_frame = ctk.CTkScrollableFrame(self, width=420, height=330)
        self.scroll_frame.pack(pady=5, padx=10)

        self.selected_process = None
        self.load_processes()

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=10)

        self.open_btn = ctk.CTkButton(btn_frame, text="Select Process", width=130, fg_color="#22c55e", command=self.confirm_select)
        self.open_btn.pack(side="left", padx=10)

        self.cancel_btn = ctk.CTkButton(btn_frame, text="Cancel", width=130, fg_color="#ef4444", command=self.destroy)
        self.cancel_btn.pack(side="right", padx=10)

    def load_processes(self):
        self.all_processes.clear()
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                pname = proc.info['name']
                pid = proc.info['pid']
                if pname and pid > 4:
                    pid_hex = hex(pid)[2:].upper().zfill(8)
                    display_text = f"[0x{pid_hex}] - {pname}"
                    self.all_processes.append((pname, pid, pid_hex, display_text))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        self.all_processes.sort(key=lambda x: x[0].lower())
        self.render_process_list(self.all_processes)

    def render_process_list(self, process_list):
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()

        for pname, pid, pid_hex, display_text in process_list:
            btn = ctk.CTkButton(
                self.scroll_frame, 
                text=display_text, 
                anchor="w",
                fg_color="#1e293b", 
                hover_color="#334155",
                font=ctk.CTkFont(family="Consolas", size=12),
                command=lambda p=pname, pd=pid: self.select_proc(p, pd)
            )
            btn.pack(fill="x", pady=2, padx=5)

    def filter_processes(self, event=None):
        query = self.search_entry.get().strip().lower()
        if query.startswith("0x"):
            query = query[2:]

        if not query:
            filtered = self.all_processes
        else:
            filtered = [
                item for item in self.all_processes 
                if query in item[0].lower() or query in item[2].lower()
            ]
        self.render_process_list(filtered)

    def select_proc(self, proc_name, pid):
        self.selected_process = (proc_name, pid)
        self.label.configure(text=f"Đã chọn: [0x{hex(pid)[2:].upper()}] {proc_name}", text_color="#4ade80")

    def confirm_select(self):
        if self.selected_process:
            self.on_select_callback(self.selected_process[0], self.selected_process[1])
            self.destroy()

class SettingsWindow(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Settings")
        self.geometry("340x360")
        self.resizable(False, False)
        self.parent = parent
        self.attributes("-topmost", True)

        self.label = ctk.CTkLabel(self, text="CÀI ĐẶT HỆ THỐNG", font=ctk.CTkFont(size=14, weight="bold"))
        self.label.pack(pady=12)

        self.color_label = ctk.CTkLabel(self, text="Chọn màu giao diện:")
        self.color_label.pack(pady=(2, 2))

        self.color_option = ctk.CTkOptionMenu(
            self, 
            values=["Mặc định (Đen Lá)", "Đen Xanh Dương", "Đen Đỏ", "Đen Tím"],
            command=self.change_bg_color
        )
        self.color_option.pack(pady=5)

        self.mode_option = ctk.CTkOptionMenu(
            self, 
            values=["Dark Mode", "Light Mode"],
            command=self.change_mode
        )
        self.mode_option.pack(pady=8)

        self.divider = ctk.CTkFrame(self, height=2, fg_color="#334155")
        self.divider.pack(fill="x", padx=20, pady=10)

        self.phone_switch = ctk.CTkSwitch(
            self, 
            text="Bật kết nối Điện thoại (Remote)",
            command=self.toggle_phone_server,
            font=ctk.CTkFont(size=12, weight="bold")
        )
        self.phone_switch.pack(pady=5)

        if self.parent.server_running:
            self.phone_switch.select()

        ip = get_local_ip()
        self.ip_info_label = ctk.CTkLabel(
            self, 
            text=f"URL Điện thoại:\nhttp://{ip}:5000", 
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#facc15"
        )
        self.ip_info_label.pack(pady=5)

    def toggle_phone_server(self):
        if self.phone_switch.get() == 1:
            self.parent.start_phone_server()
        else:
            self.parent.stop_phone_server()

    def change_bg_color(self, choice):
        colors = {
            "Mặc định (Đen Lá)": ("#0f172a", "#22c55e"),
            "Đen Xanh Dương": ("#0b132b", "#3a86ff"),
            "Đen Đỏ": ("#1a0c0c", "#ef4444"),
            "Đen Tím": ("#160c1a", "#a855f7")
        }
        bg, border = colors.get(choice, ("#0f172a", "#22c55e"))
        self.parent.main_frame.configure(fg_color=bg, border_color=border)
        self.parent.title_label.configure(text_color=border)

    def change_mode(self, choice):
        if choice == "Dark Mode":
            ctk.set_appearance_mode("Dark")
        else:
            ctk.set_appearance_mode("Light")

class InspectorWindow(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Value Inspector")
        self.geometry("340x220")
        self.resizable(False, False)
        self.parent = parent
        self.attributes("-topmost", True)

        self.label = ctk.CTkLabel(self, text="📊 GIÁ TRỊ BỘ NHỚ REALTIME", font=ctk.CTkFont(size=14, weight="bold"), text_color="#facc15")
        self.label.pack(pady=(15, 10))

        self.card_frame = ctk.CTkFrame(self, fg_color="#1e293b", corner_radius=10, border_width=1, border_color="#334155")
        self.card_frame.pack(fill="both", expand=True, padx=20, pady=(0, 15))

        self.addr_info = ctk.CTkLabel(self.card_frame, text="Địa chỉ RAM: ---", font=ctk.CTkFont(size=12), text_color="#94a3b8")
        self.addr_info.pack(pady=(12, 5))

        self.val_info = ctk.CTkLabel(self.card_frame, text="---", font=ctk.CTkFont(size=28, weight="bold"), text_color="#4ade80")
        self.val_info.pack(pady=(0, 10))

        self.status_info = ctk.CTkLabel(self.card_frame, text="Trạng thái: Đang kết nối...", font=ctk.CTkFont(size=11), text_color="#64748b")
        self.status_info.pack(pady=(0, 10))

        self.is_running = True
        self.thread = threading.Thread(target=self.update_loop, daemon=True)
        self.thread.start()

        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def update_loop(self):
        while self.is_running:
            time.sleep(0.2)
            try:
                if not self.winfo_exists(): break
                address_hex = self.parent.current_addr
                val_type = self.parent.current_type

                self.addr_info.configure(text=f"Địa chỉ: 0x{address_hex} ({val_type})")
                current_val = self.parent.read_valuable_safe()

                if self.winfo_exists():
                    if current_val != "N/A":
                        self.val_info.configure(text=current_val, text_color="#4ade80")
                        self.status_info.configure(text="● Đang theo dõi (Realtime)", text_color="#22c55e")
                    else:
                        self.val_info.configure(text="N/A", text_color="#ef4444")
                        self.status_info.configure(text="○ Lỗi đọc bộ nhớ RAM", text_color="#ef4444")
            except Exception:
                break

    def on_close(self):
        self.is_running = False
        self.destroy()

class InjectRamUI(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("INJECT RAM UI - ALL APPS")
        self.geometry("450x610")
        self.resizable(False, False)

        self.target_process = "chrome.exe"
        self.target_pid = 0
        self.process_window = None
        self.settings_window = None
        self.inspector_window = None

        self.is_frozen = False
        self.freeze_thread = None

        self.server_running = False
        self.http_server = None

        # Biến đệm dữ liệu an toàn cho Thread
        self.current_addr = "2BA09A8116C"
        self.current_val = "999"
        self.current_type = "4 Bytes (Int)"

        PhoneServerHandler.trainer_app = self

        self.ce_btn = ctk.CTkButton(
            self, text="🎯 Cheat Engine", width=110, height=28,
            fg_color="#334155", hover_color="#475569",
            font=ctk.CTkFont(size=11, weight="bold"), command=self.open_cheat_engine
        )
        self.ce_btn.place(x=120, y=10)

        self.inspector_btn = ctk.CTkButton(
            self, text="📊 Value", width=75, height=28,
            fg_color="#334155", hover_color="#475569",
            font=ctk.CTkFont(size=11, weight="bold"), command=self.open_inspector
        )
        self.inspector_btn.place(x=240, y=10)

        self.settings_btn = ctk.CTkButton(
            self, text="⚙ Settings", width=85, height=28,
            fg_color="#334155", hover_color="#475569",
            font=ctk.CTkFont(size=11, weight="bold"), command=self.open_settings
        )
        self.settings_btn.place(x=325, y=10)

        self.main_frame = ctk.CTkFrame(self, fg_color="#0f172a", corner_radius=15, border_width=2, border_color="#22c55e")
        self.main_frame.pack(fill="both", expand=True, padx=20, pady=(45, 10))

        self.title_label = ctk.CTkLabel(self.main_frame, text="INJECT RAM UI (ALL APPS)", font=ctk.CTkFont(size=18, weight="bold"), text_color="#4ade80")
        self.title_label.pack(pady=(15, 10))

        self.proc_btn = ctk.CTkButton(
            self.main_frame, text=f"Process: {self.target_process}",
            fg_color="#1e293b", hover_color="#334155", command=self.open_process_list
        )
        self.proc_btn.pack(fill="x", padx=25, pady=(0, 10))

        self.addr_label = ctk.CTkLabel(self.main_frame, text="Địa chỉ RAM (Hex):", text_color="#94a3b8", font=ctk.CTkFont(size=12))
        self.addr_label.pack(anchor="w", padx=25, pady=(0, 2))

        self.addr_entry = ctk.CTkEntry(self.main_frame, height=35)
        self.addr_entry.insert(0, self.current_addr)
        self.addr_entry.pack(fill="x", padx=25, pady=(0, 10))

        self.type_label = ctk.CTkLabel(self.main_frame, text="Kiểu dữ liệu (Value Type):", text_color="#94a3b8", font=ctk.CTkFont(size=12))
        self.type_label.pack(anchor="w", padx=25, pady=(0, 2))

        self.type_option = ctk.CTkOptionMenu(
            self.main_frame, 
            values=["4 Bytes (Int)", "Float", "Double", "8 Bytes (Int64)", "2 Bytes", "1 Byte"],
            height=32
        )
        self.type_option.pack(fill="x", padx=25, pady=(0, 10))

        self.val_label = ctk.CTkLabel(self.main_frame, text="Giá trị ghi vào RAM:", text_color="#94a3b8", font=ctk.CTkFont(size=12))
        self.val_label.pack(anchor="w", padx=25, pady=(0, 2))

        self.val_entry = ctk.CTkEntry(self.main_frame, height=35)
        self.val_entry.insert(0, self.current_val)
        self.val_entry.pack(fill="x", padx=25, pady=(0, 15))

        self.import_btn = ctk.CTkButton(
            self.main_frame, text="INJECT RAM", font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#22c55e", hover_color="#16a34a", text_color="#052e16", height=38, command=self.import_value
        )
        self.import_btn.pack(fill="x", padx=25, pady=(0, 8))

        self.freeze_btn = ctk.CTkButton(
            self.main_frame, text="❄ FREEZE", font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#0284c7", hover_color="#0369a1", text_color="#ffffff", height=38, command=self.toggle_freeze
        )
        self.freeze_btn.pack(fill="x", padx=25, pady=(0, 10))

        self.status_label = ctk.CTkLabel(self.main_frame, text="", font=ctk.CTkFont(size=12, weight="bold"))
        self.status_label.pack(pady=5)

        self.credits_label = ctk.CTkLabel(
            self, text="Created by Tuấn (Dev) & Gemini AI", 
            font=ctk.CTkFont(size=11, weight="bold", slant="italic"), text_color="#64748b"
        )
        self.credits_label.pack(side="bottom", pady=8)

        # Tự động đồng bộ cấu hình ban đầu
        self.sync_inputs()

    def sync_inputs(self):
        """Cập nhật các biến đệm từ GUI"""
        self.current_addr = self.addr_entry.get().strip()
        self.current_val = self.val_entry.get().strip()
        self.current_type = self.type_option.get()

    def read_valuable_safe(self):
        pid = self.target_pid
        if pid == 0:
            for proc in psutil.process_iter(['pid', 'name']):
                if proc.info['name'] and proc.info['name'].lower() == self.target_process.lower():
                    pid = proc.info['pid']
                    break
        return MemoryEngine.read_memory(pid, self.current_addr, self.current_type)

    def set_value_from_phone(self, new_val):
        self.current_val = str(new_val)
        self.after(0, lambda: self._update_val_entry(new_val))
        self.import_value_safe()

    def _update_val_entry(self, new_val):
        self.val_entry.delete(0, 'end')
        self.val_entry.insert(0, str(new_val))

    def import_value(self):
        self.sync_inputs()
        self.import_value_safe()

    def import_value_safe(self):
        pid = self.target_pid
        if pid == 0:
            for proc in psutil.process_iter(['pid', 'name']):
                if proc.info['name'] and proc.info['name'].lower() == self.target_process.lower():
                    pid = proc.info['pid']
                    break

        ok = MemoryEngine.write_memory(pid, self.current_addr, self.current_val, self.current_type)
        if ok:
            self.status_label.configure(text=f"✔ Đã ghi {self.current_val} vào RAM!", text_color="#4ade80")
        else:
            self.status_label.configure(text=f"❌ Không thể can thiệp {self.target_process}!", text_color="#f87171")

    def toggle_freeze(self):
        self.sync_inputs()
        self.toggle_freeze_safe()

    def toggle_freeze_safe(self):
        if not self.is_frozen:
            self.is_frozen = True
            self.freeze_btn.configure(text="🔥 UNFREEZE", fg_color="#ef4444", hover_color="#dc2626")
            self.status_label.configure(text="❄ Đã đóng băng giá trị!", text_color="#38bdf8")
            self.freeze_thread = threading.Thread(target=self.freeze_loop, daemon=True)
            self.freeze_thread.start()
        else:
            self.is_frozen = False
            self.freeze_btn.configure(text="❄ FREEZE", fg_color="#0284c7", hover_color="#0369a1")
            self.status_label.configure(text="🔥 Đã hủy đóng băng!", text_color="#f87171")

    def freeze_loop(self):
        while self.is_frozen:
            pid = self.target_pid
            if pid == 0:
                for proc in psutil.process_iter(['pid', 'name']):
                    if proc.info['name'] and proc.info['name'].lower() == self.target_process.lower():
                        pid = proc.info['pid']
                        break

            MemoryEngine.write_memory(pid, self.current_addr, self.current_val, self.current_type)
            time.sleep(0.05)

    def start_phone_server(self):
        if not self.server_running:
            self.server_running = True
            threading.Thread(target=self._run_server, daemon=True).start()
            self.status_label.configure(text="📱 Đã bật Remote (Cổng 5000)", text_color="#facc15")

    def _run_server(self):
        try:
            self.http_server = ThreadedHTTPServer(("0.0.0.0", 5000), PhoneServerHandler)
            self.http_server.serve_forever()
        except Exception:
            pass

    def stop_phone_server(self):
        if self.server_running and self.http_server:
            self.http_server.shutdown()
            self.server_running = False
            self.status_label.configure(text="📱 Đã tắt Remote", text_color="#f87171")

    def open_cheat_engine(self):
        possible_paths = [
            r"C:\Program Files\Cheat Engine 7.5\cheatengine-x86_64.exe",
            r"C:\Program Files\Cheat Engine 7.5\Cheat Engine.exe",
            r"C:\Program Files\Cheat Engine 7.4\cheatengine-x86_64.exe",
            r"C:\Program Files (x86)\Cheat Engine 7.5\cheatengine-x86_64.exe",
            r"C:\Program Files (x86)\Cheat Engine 7.5\cheatengine-i386.exe",
            r"C:\Program Files\Cheat Engine\cheatengine-x86_64.exe",
            r"C:\Program Files\Cheat Engine\Cheat Engine.exe",
        ]
        
        opened = False
        for path in possible_paths:
            if os.path.exists(path):
                subprocess.Popen([path])
                self.status_label.configure(text="✔ Đã mở Cheat Engine!", text_color="#4ade80")
                opened = True
                break

        if not opened:
            try:
                os.system("start cheatengine-x86_64.exe")
                self.status_label.configure(text="✔ Đã mở Cheat Engine!", text_color="#4ade80")
            except Exception:
                self.status_label.configure(text="❌ Không tìm thấy Cheat Engine!", text_color="#f87171")

    def open_inspector(self):
        self.sync_inputs()
        if self.inspector_window is None or not self.inspector_window.winfo_exists():
            self.inspector_window = InspectorWindow(self)
        else:
            self.inspector_window.focus()

    def open_settings(self):
        if self.settings_window is None or not self.settings_window.winfo_exists():
            self.settings_window = SettingsWindow(self)
        else:
            self.settings_window.focus()

    def open_process_list(self):
        if self.process_window is None or not self.process_window.winfo_exists():
            self.process_window = ProcessPickerWindow(self, self.set_process)
        else:
            self.process_window.focus()

    def set_process(self, proc_name, pid):
        self.target_process = proc_name
        self.target_pid = pid
        self.proc_btn.configure(text=f"Process: [0x{hex(pid)[2:].upper()}] {self.target_process}")

if __name__ == "__main__":
    app = InjectRamUI()
    app.mainloop()