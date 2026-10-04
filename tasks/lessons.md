# Lessons

## 2026-10-03: Verify long-running agent work yourself, don't relay idle pings
- Pattern: a worker said "waiting on background watchers" and went idle; I relayed that instead of checking.
- Rule: when a worker hands off to a long background job (Ghidra analysis, builds, installs), immediately check the
  real signal (log mtime, process alive, CPU) and arm a watchdog Monitor that heartbeats and alerts on hang/exit/finish.
  Re-arm on expiry until the job ends.

## 2026-10-03: Don't hand testing back to the user
- Pattern: I asked the user to playtest and to approve an emulator restart; they want me to do it.
- Rule: automate playtesting (input injection + screenshots + log) and proceed with reversible test steps without asking.

## 2026-10-03: Shared emulator = verify which instance produced the evidence
- Pattern: a worker's "boot proof" screenshot was taken while a DIFFERENT Vita3K (prebuilt, another agent's) was running;
  vpad.py matched by window title, so the evidence was ambiguous.
- Rules: (1) vpad.py now refuses to guess with several windows; pass VPAD_EXE=<path substring> and keep the printed exe
  path as proof. (2) Never `taskkill /IM Vita3K.exe` when other agents may run one; kill by PID from Get-Process Path.
  (3) When two agents need the emulator, say so in both briefs up front.
