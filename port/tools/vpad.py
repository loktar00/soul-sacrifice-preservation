"""Drive the Vita3K window: send Vita button presses as keyboard scancodes and capture screenshots.

Usage:
  python vpad.py shot <out.png>
  python vpad.py seq "cross, wait 1500, down*3, cross, hold:up:800, shot:out.png"

Step syntax (comma separated):
  <button>          tap (80 ms)       e.g. cross, start, up
  <button>*N        tap N times
  hold:<button>:ms  hold for ms
  wait <ms>         sleep
  shot:<path>       screenshot of the Vita3K window
Buttons follow the default Vita3K keyboard map in port/tools/vita3k/config.yml.
"""
import ctypes, os, sys, time
from ctypes import wintypes

user32 = ctypes.WinDLL("user32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32")
user32.SetProcessDPIAware()

# Default Vita3K bindings -> PC/AT set-1 scancodes
SCAN = {
    "cross": 0x2D, "circle": 0x2E, "square": 0x2C, "triangle": 0x2F,   # X C Z V
    "start": 0x1C, "select": 0x36,                                      # Enter, RShift
    "up": (0x48, True), "down": (0x50, True), "left": (0x4B, True), "right": (0x4D, True),
    "l": 0x10, "r": 0x12, "l2": 0x16, "r2": 0x18,                       # Q E U O
    "ls_up": 0x11, "ls_down": 0x1F, "ls_left": 0x1E, "ls_right": 0x20,  # W S A D
    "rs_up": 0x17, "rs_down": 0x25, "rs_left": 0x24, "rs_right": 0x26,  # I K J L
    "ps": 0x19,                                                          # P
}

KEYEVENTF_EXTENDEDKEY, KEYEVENTF_KEYUP, KEYEVENTF_SCANCODE = 0x1, 0x2, 0x8


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


class INPUT(ctypes.Structure):
    class _U(ctypes.Union):
        _fields_ = [("ki", KEYBDINPUT), ("pad", ctypes.c_byte * 32)]
    _anonymous_ = ("u",)
    _fields_ = [("type", wintypes.DWORD), ("u", _U)]


def exe_path(hwnd):
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    h = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid.value)  # QUERY_LIMITED_INFORMATION
    buf, size = ctypes.create_unicode_buffer(1024), wintypes.DWORD(1024)
    ctypes.windll.kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size))
    ctypes.windll.kernel32.CloseHandle(h)
    return buf.value


def find_window():
    # VPAD_EXE (substring of the emulator's exe path) picks one instance when several Vita3K builds run
    want = os.environ.get("VPAD_EXE", "").lower()
    found = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def cb(hwnd, _):
        n = user32.GetWindowTextLengthW(hwnd)
        if n and user32.IsWindowVisible(hwnd):
            buf = ctypes.create_unicode_buffer(n + 1)
            user32.GetWindowTextW(hwnd, buf, n + 1)
            if "PCSA00152" in buf.value and want in exe_path(hwnd).lower():
                found.append((hwnd, buf.value))
        return True

    user32.EnumWindows(cb, 0)
    if not found:
        sys.exit("Vita3K game window (PCSA00152) not found" + (f" for VPAD_EXE={want}" if want else ""))
    if len(found) > 1 and not want:
        sys.exit("Several Vita3K game windows open; set VPAD_EXE to pick one: " +
                 ", ".join(exe_path(h) for h, _ in found))
    print(exe_path(found[0][0]))
    return found[0]


def focus(hwnd):
    if user32.GetForegroundWindow() == hwnd:
        return
    # Alt tap lets SetForegroundWindow succeed from a background process
    user32.keybd_event(0x12, 0, 0, 0)
    user32.keybd_event(0x12, 0, KEYEVENTF_KEYUP, 0)
    user32.ShowWindow(hwnd, 9)
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.15)


def key(name, up):
    sc = SCAN[name]
    ext = False
    if isinstance(sc, tuple):
        sc, ext = sc
    flags = KEYEVENTF_SCANCODE | (KEYEVENTF_EXTENDEDKEY if ext else 0) | (KEYEVENTF_KEYUP if up else 0)
    inp = INPUT(type=1, ki=KEYBDINPUT(0, sc, flags, 0, 0))
    if user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT)) != 1:
        raise OSError(ctypes.get_last_error())


def tap(name, ms=80):
    key(name, False); time.sleep(ms / 1000); key(name, True); time.sleep(0.05)


def shot(hwnd, path):
    from PIL import Image
    r = wintypes.RECT(); user32.GetWindowRect(hwnd, ctypes.byref(r))
    w, h = r.right - r.left, r.bottom - r.top
    hdc = user32.GetWindowDC(hwnd); mdc = gdi32.CreateCompatibleDC(hdc)
    bmp = gdi32.CreateCompatibleBitmap(hdc, w, h); gdi32.SelectObject(mdc, bmp)
    user32.PrintWindow(hwnd, mdc, 2)
    buf = ctypes.create_string_buffer(w * h * 4)
    bi = (ctypes.c_uint32 * 10)(40, w, (-h) & 0xFFFFFFFF, 1 | (32 << 16), 0, 0, 0, 0, 0, 0)
    gdi32.GetDIBits(mdc, bmp, 0, h, buf, bi, 0)
    Image.frombuffer("RGBA", (w, h), buf, "raw", "BGRA", 0, 1).convert("RGB").save(path)
    gdi32.DeleteObject(bmp); gdi32.DeleteDC(mdc); user32.ReleaseDC(hwnd, hdc)
    print("shot", path)


def run(seq):
    hwnd, title = find_window()
    print(title)
    focus(hwnd)
    for step in [s.strip() for s in seq.split(",") if s.strip()]:
        if step.startswith("wait"):
            time.sleep(int(step.split()[1]) / 1000)
        elif step.startswith("shot:"):
            shot(hwnd, step[5:])
        elif step.startswith("hold:"):
            _, b, ms = step.split(":"); focus(hwnd); tap(b, int(ms))
        else:
            b, _, n = step.partition("*")
            focus(hwnd)
            for _ in range(int(n or 1)):
                tap(b); time.sleep(0.25)


if __name__ == "__main__":
    if sys.argv[1] == "shot":
        shot(find_window()[0], sys.argv[2])
    elif sys.argv[1] == "seq":
        run(sys.argv[2])
