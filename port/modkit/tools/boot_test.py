"""Boot Vita3K on the installed game, mute it, drive buttons with vpad, screenshot, then kill that instance.

  python boot_test.py <boot_wait_s> "<vpad seq>"      e.g. 40 "down, circle, wait 2500, shot:out.png"
"""
import os, subprocess, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
V3K = os.path.join(HERE, '..', '..', 'tools', 'vita3k')
sys.path.insert(0, os.path.join(HERE, '..', '..', 'tools'))
os.environ.setdefault('VPAD_EXE', os.path.join('tools', 'vita3k'))  # target the prebuilt instance, not a self-built one


def mute(pid):
    from pycaw.pycaw import AudioUtilities
    for s in AudioUtilities.GetAllSessions():
        if s.Process and s.Process.pid == pid:
            s.SimpleAudioVolume.SetMute(1, None)


def main():
    if b'Vita3K.exe' in subprocess.run(['tasklist'], capture_output=True).stdout:
        sys.exit('Vita3K is already running; not launching')
    p = subprocess.Popen([os.path.join(V3K, 'Vita3K.exe'), '-A', '-r', 'PCSA00152'], cwd=V3K)
    try:
        for _ in range(int(sys.argv[1])):
            time.sleep(1)
            try:
                mute(p.pid)
            except Exception:
                pass
        import vpad
        vpad.run(sys.argv[2])
    finally:
        p.kill()


main()
