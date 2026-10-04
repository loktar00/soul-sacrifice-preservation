# Soul Sacrifice Delta native PC port: recompilation design study (Phase 4)

Date: 2026-10-03. Input: `port/re/elf/eboot.elf` (module `efg`, PCSA00152 v01.10) and the analyzed Ghidra
project. Distribution model is "bring your own dump", as in N64Recomp and UnleashedRecomp: we ship tools and
runtime code only. No game code, no generated code from the game, and no assets are ever distributed.

## 1. Recommendation (short)

The binary suits static recompilation better than expected. It is 99.85% Thumb-2 and does not use C++
exceptions. Its EHABI table gives a complete, compiler-emitted list of function starts, and almost all of its
indirect control flow is resolvable or is plain virtual calls. The hard parts are elsewhere:

- NEON/VFP semantics: 17.6% of all instructions.
- The GXM renderer.
- The three modules the game ships beside the eboot: libc, libfios2 and libult.

**Recommended path: option (b), a hybrid built inside a Vita3K fork, staged so it can grow into (a).**

1. Start from "Vita3K as runtime" (option c). It already runs the game at 30 FPS.
2. Add an ahead-of-time Thumb-2-to-C++ recompiler whose output is called from Vita3K's CPU layer through an
   address-to-function table.
3. Keep dynarmic as both the fallback and the differential-testing oracle.
4. Retire dynarmic per module once coverage is 100% in play.
5. Keep Vita3K's GXM-to-Vulkan renderer and USSE shader recompiler. Do not reimplement them.

This makes the port runtime GPL. Vita3K's files are GPL-2.0-or-later, so the runtime can be GPL-3.0, like
UnleashedRecomp and Zelda64Recomp. The recompiler tool itself can stay MIT.

## 2. Measurements (Part A)

Method:

- Headless Ghidra 12.1.3 over a copy of the analyzed project, run with `-noanalysis -readOnly`.
- Python over the ELF for the EHABI tables.
- Scripts are in `measure/`, raw output in `measure/out/`. Re-run with
  `measure\run_measure.bat <project-copy-dir> <Script.java>` and `python measure\exidx.py`.

"Ghidra resolved" means Ghidra holds at least one flow xref on the instruction. Counts exclude the 704 ARM
import stubs (`0x81AE8xxx-0x81AEAxxx`, placeholders that are just `mvn r0,#0; bx lr`), which are the HLE
boundary.

### 2.1 Code size and instruction set

| Metric | Value | Source |
|---|---|---|
| Executable instructions (excluding stubs) | **3,592,527**; 11.08 MB of 12.4 MB text range | measure.txt |
| Thumb / ARM instructions | 3,587,139 / 5,388 (**99.85% Thumb-2**) | measure.txt |
| Ghidra functions (non-stub) | 24,984: 24,957 Thumb, 27 ARM | measure.txt |
| **EHABI exidx function starts** | **34,094**: 33,391 with the Thumb bit set, 703 without | exidx.txt |
| exidx starts Ghidra has no function for | **8,436** (25% of the real function set) | exidx.txt |
| Ghidra functions with no exidx entry | 0 | exidx.txt |
| Instructions Ghidra disassembled outside any function | 280,433 (7.8%) in 5,898 runs; 4,795 run starts are pointed to by an aligned data word | followup.txt |
| ARM-mode code | 27 small leaf functions, contiguous at `0x819DF608-0x819E5140` (~22 KB), all called directly | followup.txt |

### 2.2 Control flow

| Metric | Value | Source |
|---|---|---|
| Direct calls `bl` (T to T) | 158,457 | measure.txt |
| `blx #imm` | 24,341: 24,303 to ARM import stubs, 38 to the 27 ARM functions | measure.txt |
| Computed calls `blx reg` | 40,166 total | measure.txt |
| ...of which Ghidra resolved | 15,402. Nearly all are the SNC far-call idiom `movw/movt r12,#addr; blx r12`: 11,071 to functions, 4,119 to import stubs. These are effectively direct calls. | followup.txt |
| ...**unresolved (true indirect calls)** | **24,764**: target loaded from memory, e.g. `ldr r1,[r0]; ldr r1,[r1,#0xa0]; blx r1`, i.e. vtables and callbacks. Registers r1 9,557, r2 5,725, r3 3,279, r4 2,280, r5 1,647, lr 833 (lr used as scratch), r6-r10 ~1,350. | followup.txt, indirect_sites.csv |
| Jump tables `tbb` | 263, of which 256 resolved (1,985 cases) | measure.txt |
| Jump tables `tbh` | 1,049, of which 1,026 resolved (11,107 cases) | measure.txt |
| ARM-style tables (`ldr pc,[pc,rN]`, `add pc`) | 0 | measure.txt |
| Other computed jumps | `bx reg` not `lr`: 4 (3 resolved). `pop {pc}` as computed jump: 1 (resolved). | measure.txt |
| Returns | `pop/ldm {...,pc}` 26,310; `bx lr` 6,460 | measure.txt |
| `pop {pc}` used as a non-return (dispatch) | UNMEASURED. Ghidra models every one as a return, so it needs stack-tracking analysis. | |
| Tail calls (`b` to another function's entry) | 0 in Ghidra's model. UNMEASURED with exidx boundaries, which would expose any. | |
| Function-pointer universe | 28,547 aligned words equal a Ghidra function entry with a matching Thumb bit, pointing at 9,295 distinct functions (8,084 never directly called). 927 of the words are in `.data`. | measure.txt |
| Vtable-like tables (3 or more consecutive Thumb fn pointers) | 3,315 tables, 18,636 slots, longest 64; 3,253 sit in the read-only part of LOAD0 | followup.txt |

**Unresolved indirect-call targets.** Ghidra resolves none of the 24,764 memory-loaded calls. The candidate
target set is closed and known in advance: every exidx start (34,094) qualifies.

### 2.3 Interworking

There are no ARM-to-Thumb direct calls. Direct Thumb-to-ARM calls total 24,341: 24,303 go to import stubs,
which are HLE anyway, and 38 go to the ARM leaf block. Mode switches through `bx`/`blx reg` at runtime are
UNMEASURED. All pointer words found carry the Thumb bit that matches their target.

### 2.4 FP/SIMD (631,656 instructions = 17.6% of all)

| Class | Count |
|---|---|
| NEON only (Q registers, or integer/f32 vector on D registers, vld1-4/vst1-4) | **241,249** |
| ...arith (vmla 29k, vmul 29k, vadd 15k, vmls 5k...) | 109,301 |
| ...bitwise/select (vbif 18k, vand 10k, vbsl 10k) | 41,795 |
| ...permute/dup (vdup 29k, vzip/vuzp/vtrn/vext/vrev) | 33,307 |
| ...move | 30,878 |
| ...compare | 13,094 |
| ...convert | 6,196 |
| ...shift | 4,718 |
| ...vld1-4/vst1-4 | 1,844 |
| Shared D/S register traffic (vldr/vstr/vldm/vstm 157k, vmov core<->D 43k, vdup 3k) | 201,970 |
| VFP scalar | 188,437 |
| ...single precision (arith 18k, compare 14k, convert 3k, moves 59k) | ~94,000 |
| ...double precision (arith 149, convert 668) | 879 |
| ...register load/store | 79,299 |
| ...`vmrs` | 14,214. That equals the `vcmpe` count, so every one is `APSR_nzcv` flag transfer. |
| `vmsr` (FPSCR mode changes) | **0** |
| NEON alignment hints (`:64`/`:128`) | 0 |

Full mnemonic table: `simd_mnemonics.csv`. The profile matches Havok 2013's `hkVector4` NEON path plus
engine math.

### 2.5 Exotic instructions

| Instruction | Count | Note |
|---|---|---|
| `ldrex`/`strex` (+ `ldrexd`/`strexd`) | 787 / 787 (+2/2) | atomics, map to host CAS |
| `dmb` / `dsb` / `isb` | 4 / 0 / 0 | |
| `svc` | **0** | all syscalls go through import stubs |
| `mrc p15,0,rX,c13,c0,3` (TPIDRURO, TLS) | 74 | plus the `__tls_get_addr` import |
| `mrs`/`msr`/`mcr` | 0 | |
| Thumb `IT` instructions | 2,367; 3,169 predicated non-branch Thumb instructions | |
| ARM conditional non-branch | 113 | |
| `sdiv`/`udiv` | 0 | Cortex-A9; division goes through helpers |
| `bkpt` | 100: 99 inside functions, 77 directly after `beq` | assert traps |
| Other | `strd` 25,490, `ldrd` 6,784, `smull` 2,782, `umull` 890, `bfi`/`ubfx`/`uxtb`/`sxtb` ~2.3k each | all straightforward in C |
| Unaligned access | UNMEASURED; needs runtime tracing | harmless on x86/x64 anyway |

### 2.6 Data in code

| Metric | Value |
|---|---|
| PC-relative literal loads (`ldr`/`vldr` into text) | 16,933 loads, 13,443 distinct slots (~54 KB) |
| Literal slots overlapping a disassembled instruction | 0 |
| Literal pools are small because SNC prefers `movw/movt` | (see the r12 idiom above) |
| Ghidra "Bad Instruction" bookmarks | 8, all "flow into conflicting data" |
| Instructions disassembled inside read-only data past the code end (`0x81BD....`) | 169 (mis-disassembly) |
| Undefined bytes in text range `0x81000000-0x81BDE5AA` | 510,971, mostly code Ghidra never reached (see the 8,436 missing functions) and rodata |

### 2.7 Exceptions

- exidx has 34,094 entries: 29,273 inline pr0, 4,819 extab pr1, 2 CANTUNWIND.
- **0 generic-model entries** (no personality routine with an LSDA) and **0 pr1 entries carrying cleanup or
  catch descriptors**.
- No `__cxa_throw`, `__cxa_begin_catch`, `__gxx_personality_v0` or `_Unwind_*` anywhere.
- `std::_Xout_of_range` (1,492 sites) and `_Xlength_error` (1,486) plus `std::_Throw` (2) are Dinkumware's
  no-exceptions abort path.
- **The game does not use C++ exceptions.** The tables exist only for unwinding and backtraces. They double as
  the function-boundary oracle.

### 2.8 Threads, sync, ULT

- **Kernel imports used:**
  - Threads: sceKernelCreateThread/StartThread/DeleteThread/ExitThread/WaitThreadEnd/DelayThread
    (548 sites)/GetThreadId/GetThreadInfo/ChangeThreadVfpException.
  - Sync: LwMutex (Create/Lock/Unlock2/Delete), Mutex (126 unlock sites), Sema, EventFlag, SimpleEvent/Event
    (Set/Clear/Wait/Poll), Timer.
  - Time: GetProcessTimeLow (640 sites)/Wide.
  - Memory: SceSysmem AllocMemBlock/GetMemBlockBase/Free/FindMemBlockByAddr.
  - Full table: `imports_calls.csv`.
- **Thread creation:** 39 static sites. 7 call the import directly: the sndx audio threads and 3 sndx debug
  threads. 32 go through the game wrapper `FUN_817c86da` (`threads.csv`). Named threads include RootTask,
  4 generic workers ("thread"), VideoPlayer_AudioThread, eflSave/eflLoad/eflDelete/eflParty/eflUnlock,
  checkSaveDataThread ×3, and about 14 network/NP/adhoc/Facebook/metrics threads, which can be stubbed. The
  runtime thread count is UNMEASURED; Vita3K's log does not record creations.
- **libult:** 13 imports, 30 call sites, used by exactly **2 subsystems**: `MDL_DRAW_ULT_*` (model-draw job
  runtime, `FUN_818313e0`) and `SCE_CUSTOM_ULT_*` (`FUN_81845bc0`). Each creates one ULT runtime, its pools,
  2 queues and one ulthread-creation site.
  - This is contained, but real. ULT does user-mode context switching inside `libult.suprx`, which Vita3K
    LLE-loads from the game's `sce_module/`, together with `libc.suprx`, `libfios2.suprx` and the firmware
    `libfiber.suprx`.
  - The recompiled runtime must either recompile libult and supply a native fiber primitive underneath, or
    replace those 13 functions with a native implementation on host fibers. The second is recommended.
- **Reachability** (`reach.txt`):
  - module_start's direct-call closure is **1,821 functions using 214 imports**. It includes `sceGxmInitialize`
    (module_start, FUN_817c7028, FUN_8124a3d0, FUN_8127d63e, FUN_817ed0ee) and the RootTask/audio thread
    creation.
  - `sceDisplaySetFrameBuf` is called only from `FUN_817ecdac`, which has 0 static xrefs. It is the GXM
    display-queue callback, registered through `sceGxmInitialize` params.
  - The `sceGxmDisplayQueueAddEntry` caller is reached only through an indirect call.
  - **The first frame cannot be reached without resolving indirect calls**, which rules out a "recompile the
    static closure only" milestone.

### 2.9 HLE surface (from Ghidra + Vita3K log)

- **656 of 713 imports have call sites**, 28,429 call sites in all:
  - SceLibc: 21,302 (memcpy/malloc and similar)
  - SceLibstdcxx: 3,152
  - SceLibKernel: 1,032
  - SceThreadmgr: 806
  - SceLibm: 665
  - **SceGxm: 584 sites across all 116 imports**
- About 17 Np/Net/Adhoc/Sns libraries are dead online services and can be stubbed. SceSmart (13) can be stubbed.
- Extra modules shipped with the game: `libc.elf` (code 0x4D3BC), `libfios2.elf` (0x2B12C), `libult.elf`
  (0x1384C), `libsmart.elf` (0x1FE8CC, stub it).

### 2.10 What the numbers mean

| Usual static-recomp blocker | This binary |
|---|---|
| Function discovery | Solved by exidx: a complete compiler-emitted start list. Ghidra alone would miss 25%. |
| Jump tables | 1,312 `tbb`/`tbh` tables, 97.7% resolved by Ghidra. The remaining 30 use the same inline-table format and can be decoded by pattern. No ARM-style or register jump tables. |
| Indirect calls | 24.8k vtable/callback calls. Use an N64Recomp-style `LOOKUP_FUNC(addr)` over the 34k known starts; a miss is a bug, not a design gap. |
| Mode mixing | Negligible: 27 ARM leaf functions. |
| Exceptions/setjmp | None used. No setjmp/longjmp imports. |
| Self-modifying code / svc | None. |
| SIMD | The real cost: 241k NEON + 188k VFP + 202k shared. Needs a bit-exact NEON layer: SIMDe (MIT) or hand-written SSE/AVX, plus FTZ/default-NaN handling. vrecpe/vrsqrte estimate tables must be bit-exact. |
| Threads/fibers | About 39 thread sites plus 2 ULT runtimes. Native threads plus host fibers. |

## 3. Prior art (late 2026)

Research was delegated; URLs were checked by the research agent. Items marked "self-reported" come from the
projects' own READMEs or press.

- **N64Recomp** (MIT): MIPS to C per instruction over a context struct.
  - `jr` jump tables become switches; `jalr` becomes `LOOKUP_FUNC`; overlays are handled with relocation macros.
  - Runtime: N64ModernRuntime (**GPL-3.0**). Renderer: RT64 (MIT).
  - Zelda64Recomp (**GPL-3.0**) has a mod ecosystem (Thunderstore).
  - Links: https://github.com/N64Recomp/N64Recomp, https://github.com/N64Recomp/N64ModernRuntime,
    https://github.com/Zelda64Recomp/Zelda64Recomp
- **XenonRecomp / XenosRecomp** (MIT) and **UnleashedRecomp** (**GPL-3.0**):
  - PPC to C++ per instruction with a context struct.
  - XenonAnalyse emits TOML switch tables; indirect calls use a guest-address-to-function table placed past
    the image.
  - setjmp/longjmp are mapped to native versions; mid-asm hooks are declared in TOML.
  - Xenos shaders are recompiled to HLSL and rendered on their "plume" D3D12/Vulkan layer; the Xbox kernel is
    custom HLE.
  - Links: https://github.com/hedge-dev/XenonRecomp, https://github.com/hedge-dev/XenosRecomp,
    https://github.com/hedge-dev/UnleashedRecomp
- **Other platforms:**
  - PS3: ps3recomp (MIT; self-reported v0.12.1, Sept 2026, several titles in-game,
    https://github.com/sp00nznet/ps3recomp)
  - PS2: PS2Recomp (https://github.com/ran-j/PS2Recomp)
  - PSP: psprecomp (https://github.com/sp00nznet/psprecomp)
  - GBA (ARM7TDMI ARM+Thumb to C++, maturity unverified): gbarecomp (https://github.com/smpduong/gbarecomp)
  - NDS (pre-alpha): ndsrecomp (https://github.com/RetroPortingToolKit/ndsrecomp)
  - Switch (research-stage): SwitchRecomp (https://github.com/bgyss/SwitchRecomp)
  - 3DS: no static recompiler; Citra/Azahar are dynarmic JIT only.
- **ARM32/Thumb-2 lifters:** nothing turnkey.
  - remill (Apache-2.0): AArch32 support is "underway".
  - McSema: archived 2022.
  - anvill: AGPL, needs a closed Ghidra plugin.
  - RetDec: MIT, limited maintenance, a decompiler rather than a faithful lifter.
  - rellume: LGPL; ARM32 support unverified.
  - rev.ng: GPL; ARM32 Thumb status unverified.
  - Ghidra p-code to LLVM: academic prototypes only.
  - **Conclusion:** write a purpose-built emitter, decoding with Capstone (already in Vita3K `external/`) or
    SLEIGH.
- **PS Vita:** **no Vita static recompilation project found.** The closest is vita2hos, a Vita-to-Switch
  translation layer that runs ARM natively on the Switch. Vita3K has no CPU AOT; its only cache is the shader
  cache. This would be the first Vita recomp.
- **Vita3K:**
  - CPU backend: dynarmic only (Vita3K fork; no Unicorn in the current tree; the `external/dynarmic` submodule
    is not checked out locally).
  - Renderers: Vulkan (default) and OpenGL.
  - USSE shader recompiler: `vita3k/shader` (14.4k lines) translates to SPIR-V/GLSL.
  - Config already has `resolution-multiplier`, `fps-hack`, anisotropic filtering, texture replacement and
    shader cache.
  - **License: COPYING is GPL-2.0, and file headers say "version 2 ... or (at your option) any later version".**
    Checked locally: shader 30/30, gxm 9/9, kernel 18/18, cpu 10/10, renderer 67/69 files.
  - Sizes: renderer 25.7k lines, shader 14.4k, SceGxm module 5.9k, gxm 2.7k, kernel 6.3k.
- **dynarmic:** 0BSD (azahar-emu fork, active Sept 2026). It is an embeddable library with memory and SVC
  callbacks, and Vita3K uses it for the Cortex-A9.

## 4. Options compared

| | (a) Full static recompilation + native runtime | (b) Hybrid: AOT-recompiled code + dynarmic fallback (in a Vita3K fork) | (c) Emulator as runtime (stripped Vita3K, game-specific) |
|---|---|---|---|
| What runs the game code | Generated C++ only, no interpreter | Generated C++ for every known function; dynarmic for misses | dynarmic JIT |
| Effort (1 experienced dev, rough) | 9-18 months | 6-12 months to full coverage, but useful at every step | 1-2 months |
| Main risk | Any miss (wrong NEON op, unknown entry, ULT context trick) is a crash with no fallback; long debug loop | NEON correctness (mitigated by differential testing against dynarmic); integration with Vita3K's thread/CPU state | Low: it already runs at 30 FPS with one known particle bug |
| CPU performance | Best | Near (a) once coverage is about 100% | Already sufficient (30 FPS locked) |
| Resolution | Vita3K renderer reused: multiplier, AA, AF | same | same (already in Vita3K) |
| Framerate unlock | Easiest to patch game logic in source-like C++ | same (patch recompiled functions) | `fps-hack` plus binary patches; game logic is frame-locked (`FPS 30` in boot_config.ini), UNMEASURED whether 60 is stable |
| Mods | Loose files (already work) plus function hooks/overrides in C++, mid-function hooks as in XenonRecomp | same | Loose files plus Vita3K patch files only |
| Input | Native (SDL), remappable, mouse camera possible via hooks | same | SDL via Vita3K; mouse camera needs hacks |
| Vita3K reuse | GXM/renderer/shader, HLE modules, memory map; kernel/thread layer rewritten | Almost all of Vita3K; adds an AOT dispatch layer in `vita3k/cpu` | All of it |
| License of the port runtime | GPL (if any Vita3K code is used); fully permissive only if GXM/USSE is reimplemented (person-years) | GPL-3.0 (Vita3K is GPL-2.0+) | GPL |
| Distribution | Generated code is a derivative of the game, so it must be generated and compiled on the user's machine | same; the dynarmic fallback means a partial build still runs | Nothing generated; ships as an emulator build |

**Licensing consequences.**

- Taking any Vita3K code makes the port runtime a GPL derivative. Choose GPL-3.0, which GPL-2.0-or-later
  permits, matching UnleashedRecomp and Zelda64Recomp.
- The recompiler (ELF/exidx parser, Thumb-2 emitter) can be a separate MIT tool, because it shares no code
  with the runtime.
- GPL has no bearing on the user's own dump. What matters for us is that the generated C++ and any binary
  compiled from it are derived from the game. Under the "never distribute game code" rule, they must be built
  locally.
- Practical consequence: ship a self-contained toolchain with the installer. Options:
  - `zig cc`, a single roughly 50 MB download bundling clang.
  - An in-process LLVM AOT.
- With that toolchain, the "install" step is: verify the dump hash, decrypt with the user's rif, recompile,
  compile, then cache the result. The compile time for about 3.6M generated statements is **UNMEASURED**;
  measure it in M1.

## 5. GXM graphics on PC

**Reuse Vita3K's GXM layer.** That is the `SceGxm` HLE module, `vita3k/gxm`, the Vulkan renderer and the USSE
shader recompiler.

- **Why reuse:**
  - The USSE-to-SPIR-V translator is the single hardest piece of Vita emulation.
  - It already renders this game correctly, including the shaders seen in the logs (`iDiffuseCol0`,
    `WorldVPXf`), except one particle/fog blend artifact.
  - It already has resolution scaling, anisotropic filtering, texture replacement, shader cache and async
    pipeline compilation.
- **Improvements to make on top:**
  - Translate all GXP programs ahead of time at install, so there is no in-game stutter.
  - Fix the particle artifact upstream.
  - Hook post-process passes in recompiled code for higher-quality bloom/shadows.
  - Raise the internal render-target size beyond the multiplier where the game hard-codes 960x544 viewports.
    Find those sites through the 584 GXM call sites.
- **Reimplementing** only pays off if a permissive license is a hard requirement. It means writing a new USSE
  decompiler, which is months to years of work and duplicates Vita3K.
- **A middle path is not recommended:** dumping the game's shaders at install, translating them with Vita3K's
  translator run as a separate GPL tool, and shipping a permissive renderer. The GXM state machine (surface
  sync, memory-mapped render targets) is just as tied to Vita3K.

## 6. Milestone plan

### M1: "AQL splash rendered with native code in the loop" (proves the approach)

The first frame cannot be reached by recompiling only module_start's static closure (section 2.8). The display
callback and the queue-add path are indirect. The milestone therefore runs **inside the Vita3K fork with the
dynarmic fallback** and measures how much of the boot executes natively.

1. **Function list.** Parse exidx to get 34,094 starts and their modes. Cross-check with Ghidra's 24,984;
   expected misses: 8,436.
2. **Decoder and emitter.** Capstone Thumb-2/ARM decoding feeding a C++ emitter, one statement per instruction
   over a `GuestCtx` (r0-r15, NZCV/Q/GE flags, `d0-d31` as a union with `s`/`q` views, FPSCR, IT state).
   Guest memory access goes through `base + (uint32_t)addr`, matching Vita3K's existing host reservation.
3. **Control flow:**
   - `bl`/`blx #imm` become direct C++ calls.
   - Calls to stub addresses become the HLE thunk.
   - `blx reg` and `pop {pc}` to a non-matching return address go through `LOOKUP_FUNC`.
   - `tbb`/`tbh` become `switch` statements over the decoded inline table.
   - `IT` blocks become `if` statements.
4. **Scope v1:** the integer, VFP-scalar, `ldrex`/`strex` (host CAS) and TPIDRURO subset. Any function
   containing NEON stays on dynarmic in M1. The NEON count per function is measured as part of this step.
5. **Dispatch hook in Vita3K's CPU layer:**
   - Before dynarmic enters a block, look its address up in the AOT table and call native if present.
   - Native code calls a guest address that is missing from the table by running dynarmic with LR set to a
     sentinel, then halting on return.
6. **Differential mode.** Per function, snapshot the context, run native, run dynarmic on a copy, and compare
   registers plus written memory. Log mismatches. This is the NEON safety net later.
7. **Gate:**
   - Boot to the AQL splash with the AOT DLL loaded.
   - Report the share of executed guest instructions that ran natively, aiming for at least 80% at the splash.
   - Report the compile time and DLL size of a full-binary build.
   - Zero differential mismatches over 1,000 boot frames.

### M2: full eboot coverage

- Add NEON through SIMDe or hand-written SSE4/AVX2, with FTZ/default-NaN matching ARM NEON.
- Add the 27 ARM functions.
- Run differential testing across the debug Stage Select quests.
- Exit criterion: zero dynarmic entries during a full quest.

### M3: native runtime

- Replace the LLE-loaded `libult` with host fibers behind the 13 imported entry points.
- Replace `libc`/`libfios2` with native HLE, or run them through the same recompiler.
- Stub Np/Net/Smart.
- Strip the Qt GUI and make a single-game launcher.
- Build the install flow: dump verification, recompile, local compile.

### M4: PC features

- Render-scale and UI scaling.
- 60 FPS experiment: find the frame-step constants behind `FPS 30`.
- Remappable input and mouse camera.
- C++ mod hooks alongside the loose-file mods that already work.

## 7. Risks

1. **NEON/VFP bit-exactness** (631k FP/SIMD instructions). Wrong estimates or denormal behaviour cause physics
   (Havok) desyncs. Mitigation: differential testing against dynarmic (M1 step 6).
2. **Generated-code volume.** About 3.6M statements; compile time and DLL size are UNMEASURED. Mitigation:
   split per 64 KB region, compile in parallel, cache.
3. **Hidden control flow** that the measurements could not see:
   - `pop {pc}` used for dispatch
   - tail calls under exidx boundaries
   - Thumb/ARM switches through pointers

   The dynarmic fallback contains all three.
4. **Threads and ULT.** Vita3K's thread model is tied to its per-thread CPU state. Native code needs a
   per-thread `GuestCtx`, plus host fibers for ULT.
5. **GPL scope.** The whole runtime is GPL-3.0, and the port cannot be relicensed permissively without
   replacing the Vita3K-derived parts.
6. **Legal and distribution.** Generated code must never ship, so a local toolchain is mandatory, which adds
   UX and support cost.
7. **Frame-locked logic.** A 60 FPS unlock may need game-logic patches. The FPS 30 path has not been studied.

## 8. Files

- `measure/RecompMeasure.java`: instruction sweep, indirect flow, SIMD classes, exotic ops, data in code,
  pointer universe, import call counts. Outputs `out/measure.txt`, `indirect_sites.csv`, `simd_mnemonics.csv`,
  `imports_calls.csv`, `thread_sites.csv`.
- `measure/RecompFollowup.java`: what resolved computed calls point at, layout per 64 KB, out-of-function runs,
  `bkpt` and bad-instruction sites, vtable runs, ARM functions. Output: `out/followup.txt`.
- `measure/RecompFunctions.java`: writes `out/functions.csv`.
- `measure/RecompReach.java`: module_start reachability. Output: `out/reach.txt`.
- `measure/RecompThreads.java`: thread-wrapper call sites with names. Output: `out/threads.csv`.
- `measure/exidx.py`: EHABI classification and the exidx-vs-Ghidra function comparison. Output: `out/exidx.txt`.
- `measure/run_measure.bat`: read-only headless launcher. The project copy used was in the session scratchpad;
  the real project was not opened.
