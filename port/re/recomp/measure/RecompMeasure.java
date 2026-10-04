// Measures eboot.elf for static-recompilation feasibility. Read-only: run headless with
//   -process eboot.elf -noanalysis -readOnly -postScript RecompMeasure.java
// Writes measure.txt, imports_calls.csv, thread_sites.csv, simd_mnemonics.csv, indirect_sites.csv
// into port\re\recomp\measure\out.
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.*;
import ghidra.program.model.lang.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.mem.*;
import ghidra.program.model.pcode.*;
import ghidra.program.model.scalar.Scalar;
import ghidra.program.model.symbol.*;
import java.io.*;
import java.math.BigInteger;
import java.util.*;
import java.util.regex.*;

public class RecompMeasure extends GhidraScript {
	static final File OUT = new File("E:/soul sacrifice/port/re/recomp/measure/out");
	static final File IMPORTS = new File("E:/soul sacrifice/port/re/ghidra/imports.csv");
	static final Pattern COND = Pattern.compile("(eq|ne|cs|cc|hs|lo|mi|pl|vs|vc|hi|ls|ge|lt|gt|le)$");
	static final Set<String> SUSPICIOUS = new HashSet<>(Arrays.asList("cdp", "cdp2", "ldc", "ldc2", "ldcl",
			"stc", "stc2", "stcl", "mcr2", "mrc2", "mcrr", "mcrr2", "mrrc", "mrrc2", "swp", "swpb", "bkpt", "udf",
			"smc", "hvc", "setend", "rfe", "rfeia", "rfedb", "srs", "srsia", "srsdb", "cps", "cpsid", "cpsie",
			"sdiv", "udiv", "wfi", "wfe", "sev", "yield", "dbg"));

	Listing listing;
	Register tmode;
	ProgramContext ctx;
	FunctionManager fm;
	ReferenceManager rm;
	PrintWriter log;
	Map<String, Long> counters = new TreeMap<>();

	void inc(String k) { inc(k, 1); }
	void inc(String k, long n) { counters.merge(k, n, Long::sum); }

	int mode(Address a) {
		BigInteger v = ctx.getValue(tmode, a, false);
		return v == null ? -1 : v.intValue();
	}

	// Mnemonics whose tail only looks like a condition code (mls ends in "ls", vcgt in "gt", ...).
	static final Set<String> NOT_COND = new HashSet<>(Arrays.asList("mls", "vmls", "vnmls", "vcgt", "vcge", "vcle",
			"vclt", "vceq", "vacge", "vacgt", "vacle", "vaclt", "vcls", "teq", "smlals", "umlals", "vmlals"));

	static String core(String b) {
		if (NOT_COND.contains(b)) return b;
		Matcher m = COND.matcher(b);
		if (m.find() && m.start() > 0) {
			String s = b.substring(0, m.start());
			if (!NOT_COND.contains(b) && !s.equals("v") && !s.equals("b")) return s;
		}
		return b;
	}

	static String base(String mnem) {
		String m = mnem.toLowerCase();
		int dot = m.indexOf('.');
		return dot < 0 ? m : m.substring(0, dot);
	}

	@Override
	public void run() throws Exception {
		OUT.mkdirs();
		listing = currentProgram.getListing();
		fm = currentProgram.getFunctionManager();
		rm = currentProgram.getReferenceManager();
		ctx = currentProgram.getProgramContext();
		tmode = ctx.getRegister("TMode");
		Memory mem = currentProgram.getMemory();
		log = new PrintWriter(new File(OUT, "measure.txt"), "UTF-8");

		// ---- memory layout
		AddressSet exec = new AddressSet();
		for (MemoryBlock b : mem.getBlocks()) {
			log.printf("block %-12s %s-%s size=0x%x r%s w%s x%s init=%s%n", b.getName(), b.getStart(), b.getEnd(),
					b.getSize(), b.isRead() ? "+" : "-", b.isWrite() ? "+" : "-", b.isExecute() ? "+" : "-",
					b.isInitialized());
			if (b.isExecute() && b.isInitialized()) exec.add(b.getStart(), b.getEnd());
		}

		// ---- imports (stub address -> lib/name), their stub function ranges are excluded from code stats
		Map<Address, String[]> imp = new HashMap<>();
		AddressSet stubs = new AddressSet();
		try (BufferedReader r = new BufferedReader(new FileReader(IMPORTS))) {
			r.readLine();
			for (String line; (line = r.readLine()) != null;) {
				String[] f = line.split(",", -1);
				Address a = toAddr(Long.parseLong(f[3], 16));
				imp.put(a, new String[] { f[0], f[2] });
				Function sf = fm.getFunctionAt(a);
				if (sf != null && a.getOffset() < 0xff000000L) stubs.add(sf.getBody());
			}
		}

		// ---- functions by mode, reference profile
		long fnTotal = 0, fnThumb = 0, fnArm = 0, fnUnk = 0, fnThunk = 0, fnStub = 0;
		long fnCalled = 0, fnDataOnly = 0, fnNoRefs = 0;
		Map<Address, Integer> fnMode = new HashMap<>();
		for (Function f : fm.getFunctions(true)) {
			if (f.isExternal()) continue;
			fnTotal++;
			Address e = f.getEntryPoint();
			if (stubs.contains(e)) { fnStub++; continue; }
			int m = mode(e);
			fnMode.put(e, m);
			if (m == 1) fnThumb++; else if (m == 0) fnArm++; else fnUnk++;
			if (f.isThunk()) fnThunk++;
			boolean call = false, data = false;
			for (Reference ref : rm.getReferencesTo(e)) {
				RefType t = ref.getReferenceType();
				if (t.isCall() || t.isJump()) call = true; else data = true;
			}
			if (call) fnCalled++; else if (data) fnDataOnly++; else fnNoRefs++;
		}
		log.println();
		log.printf("functions_total=%d import_stubs=%d thumb=%d arm=%d unknown_mode=%d thunks=%d%n", fnTotal, fnStub,
				fnThumb, fnArm, fnUnk, fnThunk);
		log.printf("functions_with_call_or_jump_xref=%d data_xref_only=%d no_xref=%d%n", fnCalled, fnDataOnly, fnNoRefs);

		// ---- instruction sweep
		Map<String, Long> simd = new TreeMap<>();
		Map<String, Long> exotic = new TreeMap<>();
		Map<String, Long> indirect = new TreeMap<>();
		Map<String, Long> returns = new TreeMap<>();
		Set<String> mrcForms = new TreeSet<>();
		PrintWriter ind = new PrintWriter(new File(OUT, "indirect_sites.csv"), "UTF-8");
		ind.println("address,mode,kind,mnemonic,operands,resolved_targets,function");
		long insTotal = 0, insThumb = 0, insArm = 0, insOutsideFn = 0, codeBytes = 0;
		Address maxIns = null;
		InstructionIterator it = listing.getInstructions(exec, true);
		while (it.hasNext()) {
			if (monitor.isCancelled()) break;
			Instruction in = it.next();
			Address a = in.getAddress();
			if (stubs.contains(a)) { inc("stub_instructions"); continue; }
			insTotal++;
			codeBytes += in.getLength();
			maxIns = a;
			int m = mode(a);
			if (m == 1) insThumb++; else insArm++;
			String ms = m == 1 ? "T" : "A";
			Function fn = fm.getFunctionContaining(a);
			if (fn == null) insOutsideFn++;
			String mn = in.getMnemonicString().toLowerCase();
			String b = base(mn);
			FlowType ft = in.getFlowType();

			// --- control flow
			if (ft.isComputed()) {
				int resolved = 0;
				for (Reference ref : in.getReferencesFrom()) if (ref.getReferenceType().isFlow()) resolved++;
				String kind;
				if (b.startsWith("tbb") || b.startsWith("tbh")) kind = "jumptable_" + b.substring(0, 3);
				else if (ft.isCall()) kind = "call";
				else if (ft.isJump()) kind = "jump";
				else kind = "other_" + ft;
				String bucket = kind + "_" + (b.matches("^(bx|blx).*") ? b.substring(0, b.startsWith("blx") ? 3 : 2) : b);
				indirect.merge(bucket + (resolved > 0 ? "_resolved" : "_unresolved"), 1L, Long::sum);
				if (kind.startsWith("jumptable")) inc(kind + "_cases", resolved);
				ind.printf("%s,%s,%s,%s,\"%s\",%d,%s%n", a, ms, kind, mn, ops(in), resolved,
						fn == null ? "" : fn.getName());
			} else if (ft.isTerminal()) {
				String what = b;
				if (b.equals("bx") || b.equals("mov")) what = b + " " + ops(in);
				else if (b.startsWith("pop") || b.startsWith("ldm")) what = "pop/ldm {...,pc}";
				else if (b.startsWith("ldr")) what = "ldr pc,...";
				returns.merge(what, 1L, Long::sum);
			} else if (ft.isCall()) {
				Address[] fl = in.getFlows();
				if (fl.length == 1) {
					Address t = fl[0];
					int tm = imp.containsKey(t) ? -2 : mode(t);
					if (imp.containsKey(t)) inc("direct_calls_to_import_stubs");
					else if (tm == m) inc("direct_calls_same_mode_" + ms);
					else inc("direct_calls_mode_switch_" + ms + "->" + (tm == 1 ? "T" : tm == 0 ? "A" : "?"));
					inc("direct_calls_mnemonic_" + b);
				}
			} else if (ft.isJump() && !ft.isConditional()) {
				Address[] fl = in.getFlows();
				if (fl.length == 1 && fn != null) {
					Function tf = fm.getFunctionAt(fl[0]);
					if (tf != null && !tf.equals(fn)) {
						inc("tail_calls_b_to_other_function");
						if (mode(fl[0]) != m) inc("tail_calls_mode_switch");
					}
				}
			} else if (ft.isJump() && ft.isConditional()) {
				Address[] fl = in.getFlows();
				if (fl.length == 1 && fn != null) {
					Function tf = fm.getFunctionAt(fl[0]);
					if (tf != null && !tf.equals(fn)) inc("conditional_tail_calls");
				}
			}

			// --- conditional execution (non-branch instructions guarded by a condition)
			if (b.matches("^it[te]{0,3}$")) inc("thumb_it_instructions");
			if (!ft.isJump() && !ft.isCall() && !ft.isTerminal() && isPredicated(in)) inc("predicated_nonbranch_" + ms);

			// --- exotic
			if (b.startsWith("ldrex") || b.startsWith("strex") || b.startsWith("clrex") || b.equals("dmb")
					|| b.equals("dsb") || b.equals("isb") || b.equals("svc") || b.equals("swi") || b.startsWith("mrc")
					|| b.startsWith("mcr") || b.equals("mrs") || b.equals("msr") || b.startsWith("pld")
					|| b.startsWith("pli") || b.equals("clz") || b.startsWith("rev") || b.startsWith("rbit")
					|| b.startsWith("ssat") || b.startsWith("usat") || b.startsWith("ldrd") || b.startsWith("strd")
					|| b.startsWith("umull") || b.startsWith("smull") || b.startsWith("umlal") || b.startsWith("smlal")
					|| b.startsWith("bfi") || b.startsWith("bfc") || b.startsWith("ubfx") || b.startsWith("sbfx")
					|| b.startsWith("uxt") || b.startsWith("sxt") || b.startsWith("sel") || b.startsWith("qadd")
					|| b.startsWith("qsub") || b.startsWith("uadd") || b.startsWith("usub") || b.startsWith("sadd")
					|| b.startsWith("smla") || b.startsWith("smul") || b.startsWith("mls")) {
				exotic.merge(core(b), 1L, Long::sum);
				if (b.startsWith("mrc") || b.startsWith("mcr") || b.equals("mrs") || b.equals("msr") || b.equals("svc"))
					mrcForms.add(mn + " " + ops(in));
			}
			if (SUSPICIOUS.contains(b) || SUSPICIOUS.contains(core(b))) {
				inc("suspicious_" + b);
			}

			// --- FP/SIMD
			if (b.startsWith("v") || b.startsWith("fld") || b.startsWith("fst") || b.startsWith("fmstat")) {
				String cls = simdClass(in, mn, b);
				simd.merge(cls, 1L, Long::sum);
				simd.merge("mnem\t" + cls.substring(0, cls.indexOf(':')) + "\t" + b, 1L, Long::sum);
			}
			if (ops(in).matches(".*:(64|128|256)\\].*")) inc("neon_alignment_hints");
		}
		ind.close();

		log.println();
		log.printf("instructions_total=%d thumb=%d arm=%d outside_any_function=%d code_bytes=%d last_instruction=%s%n",
				insTotal, insThumb, insArm, insOutsideFn, codeBytes, maxIns);
		dump("indirect control flow (computed flow, by kind/mnemonic, resolved = Ghidra has >=1 flow xref)", indirect);
		dump("returns / terminators", returns);
		dump("exotic / notable integer instructions", exotic);
		log.println("\n## mrc/mcr/mrs/msr/svc forms");
		for (String s : mrcForms) log.println("  " + s);
		Map<String, Long> simdCls = new TreeMap<>(), simdMn = new TreeMap<>();
		for (Map.Entry<String, Long> e : simd.entrySet())
			(e.getKey().startsWith("mnem\t") ? simdMn : simdCls).put(e.getKey(), e.getValue());
		dump("FP/SIMD by class", simdCls);
		try (PrintWriter w = new PrintWriter(new File(OUT, "simd_mnemonics.csv"), "UTF-8")) {
			w.println("unit,mnemonic,count");
			for (Map.Entry<String, Long> e : simdMn.entrySet())
				w.println(e.getKey().substring(5).replace('\t', ',') + "," + e.getValue());
		}

		// ---- data in code range
		AddressSet textRange = new AddressSet(exec.getMinAddress(), maxIns);
		Map<String, Long> dataTypes = new TreeMap<>();
		long dataBytes = 0, dataInsideFnRange = 0, dataItems = 0;
		DataIterator di = listing.getDefinedData(textRange, true);
		while (di.hasNext()) {
			Data d = di.next();
			dataItems++;
			dataBytes += d.getLength();
			String tn = d.isPointer() ? "pointer" : d.hasStringValue() ? "string" : d.getDataType().getName();
			dataTypes.merge(tn, 1L, Long::sum);
			Function f = fm.getFunctionContaining(d.getAddress());
			if (f != null) dataInsideFnRange++;
		}
		long textBytes = textRange.getNumAddresses();
		log.println("\n## data inside code range " + exec.getMinAddress() + "-" + maxIns);
		log.printf("text_range_bytes=%d instruction_bytes=%d defined_data_items=%d defined_data_bytes=%d " +
				"data_items_inside_function_bodies=%d undefined_bytes=%d%n", textBytes, codeBytes, dataItems, dataBytes,
				dataInsideFnRange, textBytes - codeBytes - dataBytes - stubs.getNumAddresses());
		dumpInline("data types in code range", dataTypes);

		// literal-pool loads: pc-relative ldr/vldr whose target is in the code range
		long litLoads = 0;
		Set<Address> litTargets = new HashSet<>();
		it = listing.getInstructions(textRange, true);
		while (it.hasNext()) {
			Instruction in = it.next();
			String b = base(in.getMnemonicString());
			if (!(b.startsWith("ldr") || b.startsWith("vldr"))) continue;
			for (Reference ref : in.getReferencesFrom()) {
				if (ref.getReferenceType().isRead() && textRange.contains(ref.getToAddress())) {
					litLoads++;
					litTargets.add(ref.getToAddress());
				}
			}
		}
		long litOnIns = 0;
		for (Address t : litTargets) if (listing.getInstructionContaining(t) != null) litOnIns++;
		log.printf("literal_pool_loads=%d distinct_literal_slots=%d literal_slots_overlapping_an_instruction=%d%n",
				litLoads, litTargets.size(), litOnIns);

		Map<String, Long> bms = new TreeMap<>();
		Iterator<Bookmark> bit = currentProgram.getBookmarkManager().getBookmarksIterator();
		while (bit.hasNext()) {
			Bookmark bm = bit.next();
			if (bm.getTypeString().equals("Error") || bm.getTypeString().equals("Warning"))
				bms.merge(bm.getTypeString() + " / " + bm.getCategory(), 1L, Long::sum);
		}
		dump("error/warning bookmarks", bms);

		// ---- function pointer universe: aligned words anywhere in initialized memory that equal a function entry
		long ptrWords = 0, ptrWordsInData = 0;
		Set<Address> ptrTargets = new HashSet<>();
		Set<Address> ptrTargetsDataOnly = new HashSet<>();
		for (MemoryBlock blk : mem.getBlocks()) {
			if (!blk.isInitialized() || blk.getStart().getOffset() < 0x81000000L) continue;
			byte[] buf = new byte[(int) blk.getSize()];
			blk.getBytes(blk.getStart(), buf);
			for (int i = 0; i + 4 <= buf.length; i += 4) {
				long v = (buf[i] & 0xffL) | (buf[i + 1] & 0xffL) << 8 | (buf[i + 2] & 0xffL) << 16 | (buf[i + 3] & 0xffL) << 24;
				if (v < 0x81000000L || v >= 0x81000000L + 0xC4D200L) continue;
				Address t = toAddr(v & ~1L);
				Function f = fm.getFunctionAt(t);
				if (f == null || stubs.contains(t)) continue;
				Integer fmode = fnMode.get(t);
				if (fmode == null || fmode != (int) (v & 1)) continue;
				Address at = blk.getStart().add(i);
				if (textRange.contains(at) && listing.getInstructionContaining(at) != null) continue; // opcode bytes
				ptrWords++;
				ptrTargets.add(t);
				if (!blk.isExecute()) ptrWordsInData++;
			}
		}
		log.println("\n## function-pointer universe (aligned words == function entry | Thumb bit, not inside instructions)");
		log.printf("pointer_words=%d in_writable_data=%d distinct_target_functions=%d%n", ptrWords, ptrWordsInData,
				ptrTargets.size());
		long ptrNoCallRef = 0;
		for (Address t : ptrTargets) {
			boolean call = false;
			for (Reference ref : rm.getReferencesTo(t)) if (ref.getReferenceType().isCall()) call = true;
			if (!call) ptrNoCallRef++;
		}
		log.printf("pointer_targets_never_directly_called=%d%n", ptrNoCallRef);

		// ---- imports: call-site counts
		Map<Address, Integer> importCalls = new HashMap<>();
		try (PrintWriter w = new PrintWriter(new File(OUT, "imports_calls.csv"), "UTF-8")) {
			w.println("library,name,stub,call_sites,data_refs");
			for (Map.Entry<Address, String[]> e : imp.entrySet()) {
				int calls = 0, data = 0;
				for (Reference ref : rm.getReferencesTo(e.getKey())) {
					if (stubs.contains(ref.getFromAddress())) continue;
					if (ref.getReferenceType().isCall() || ref.getReferenceType().isJump()) calls++; else data++;
				}
				importCalls.put(e.getKey(), calls);
				w.printf("%s,\"%s\",%s,%d,%d%n", e.getValue()[0], e.getValue()[1], e.getKey(), calls, data);
			}
		}

		// ---- thread / ult / exception call sites with nearby string arguments
		Pattern interesting = Pattern.compile("sceKernelCreateThread|sceKernelStartThread|_sceUlt.*Create|sceUlt.*|"
				+ "std::_Throw|std::_X.*|std::exception.*|std::runtime_error.*|sceKernelCreate(Sema|Mutex|LwMutex|EventFlag|SimpleEvent|Timer)");
		try (PrintWriter w = new PrintWriter(new File(OUT, "thread_sites.csv"), "UTF-8")) {
			w.println("import,call_site,caller,nearby_string,thumb_entry_arg");
			for (Map.Entry<Address, String[]> e : imp.entrySet()) {
				if (!interesting.matcher(e.getValue()[1]).matches()) continue;
				for (Reference ref : rm.getReferencesTo(e.getKey())) {
					if (!ref.getReferenceType().isCall() && !ref.getReferenceType().isJump()) continue;
					Address site = ref.getFromAddress();
					Function caller = fm.getFunctionContaining(site);
					String[] near = nearbyArgs(site);
					w.printf("%s,%s,%s,\"%s\",%s%n", e.getValue()[1], site, caller == null ? "" : caller.getName(),
							near[0].replace("\"", "'"), near[1]);
				}
			}
		}

		// ---- exception-related symbols
		log.println("\n## exception-related symbols (name match), with xref counts");
		Pattern exc = Pattern.compile(".*(cxa_|_Unwind|personality|aeabi_unwind|_Throw|terminate|__cxa).*");
		for (Symbol s : currentProgram.getSymbolTable().getAllSymbols(true)) {
			if (!exc.matcher(s.getName()).matches()) continue;
			log.printf("  %s @%s refs=%d%n", s.getName(true), s.getAddress(), rm.getReferenceCountTo(s.getAddress()));
		}

		dump("counters", counters);
		log.close();
		println("RecompMeasure done: " + OUT);
	}

	String ops(Instruction in) {
		StringBuilder sb = new StringBuilder();
		for (int i = 0; i < in.getNumOperands(); i++) {
			if (i > 0) sb.append(',');
			sb.append(in.getDefaultOperandRepresentation(i));
		}
		return sb.toString().replace("\"", "'");
	}

	// A non-branch instruction whose p-code starts by skipping itself (ARM COND / Thumb IT predicate).
	boolean isPredicated(Instruction in) {
		Address next = in.getMaxAddress().next();
		for (PcodeOp op : in.getPcode()) {
			if (op.getOpcode() == PcodeOp.CBRANCH) {
				Varnode t = op.getInput(0);
				if (t.isAddress() && t.getAddress().equals(next)) return true;
			}
		}
		return false;
	}

	String simdClass(Instruction in, String mn, String b) {
		boolean q = false, d = false, s = false;
		for (int i = 0; i < in.getNumOperands(); i++) {
			for (Object o : in.getOpObjects(i)) {
				if (!(o instanceof Register)) continue;
				String n = ((Register) o).getName().toLowerCase();
				if (n.matches("q\\d+")) q = true;
				else if (n.matches("d\\d+")) d = true;
				else if (n.matches("s\\d+")) s = true;
			}
		}
		String r = ops(in).toLowerCase();
		if (r.matches(".*\\bq\\d+.*")) q = true;
		if (r.matches(".*\\bd\\d+.*")) d = true;
		if (r.matches(".*\\bs\\d+.*")) s = true;
		String types = mn.contains(".") ? mn.substring(mn.indexOf('.')) : "";
		String core = core(b).replaceAll("^vzip\\d+$", "vzip");
		if (core.matches("vld[1-4]|vst[1-4]")) return "NEON:load/store (vld1-4/vst1-4)";
		if (core.matches("vldr|vstr|vldm.*|vstm.*|vpush|vpop|fld.*|fst.*"))
			return (s && !d ? "VFP" : "VFP/NEON") + ":register load/store (vldr/vstr/vldm/vstm/vpush/vpop)";
		if (core.matches("vmrs|vmsr|fmstat")) return "VFP:status (vmrs/vmsr)";
		if (q) return "NEON:" + neonGroup(core);
		if (types.contains("f64") || (d && !s && types.matches("\\.f(32|64)\\.f(32|64)") && types.contains("64")))
			return "VFP:double " + vfpGroup(core);
		if (s && !q && !(d && types.matches(".*\\.(i|s|u|p)\\d+.*"))) return "VFP:single " + vfpGroup(core);
		if (core.equals("vmov") || core.equals("vdup")) return "VFP/NEON:" + (core.equals("vdup") ? "dup" : "move/transfer");
		if (d) return "NEON:" + neonGroup(core) + " (64-bit D)";
		return "OTHER:" + core;
	}

	static String vfpGroup(String c) {
		if (c.matches("vadd|vsub|vmul|vdiv|vnmul|vmla|vmls|vnmla|vnmls|vfma|vfms|vfnma|vfnms|vneg|vabs|vsqrt"))
			return "arith";
		if (c.matches("vcmp|vcmpe")) return "compare";
		if (c.startsWith("vcvt")) return "convert";
		if (c.equals("vmov")) return "move/transfer";
		return "other(" + c + ")";
	}

	static String neonGroup(String c) {
		if (c.matches("vadd|vsub|vmul|vmla|vmls|vfma|vfms|vabs|vneg|vmax|vmin|vpadd|vpmax|vpmin|vrecpe|vrecps|vrsqrte|vrsqrts|vqadd|vqsub|vhadd|vrhadd|vabd|vaddl|vaddw|vsubl|vmull|vmlal|vqdmulh|vpaddl|vaddhn|vabdl|vqrdmulh|vmovn|vqmovn|vqmovun|vmovl|vrshrn|vshrn|vqshrn|vqrshrn"))
			return "arith";
		if (c.matches("vand|vorr|veor|vbic|vorn|vbsl|vbit|vbif|vmvn|vtst")) return "bitwise";
		if (c.matches("vceq|vcge|vcgt|vcle|vclt|vacge|vacgt")) return "compare";
		if (c.matches("vshl|vshr|vsra|vrshr|vsli|vsri|vqshl|vrshl|vqrshl|vshll")) return "shift";
		if (c.matches("vzip|vuzp|vtrn|vrev\\d*|vext|vtbl|vtbx|vswp|vdup")) return "permute";
		if (c.startsWith("vcvt")) return "convert";
		if (c.equals("vmov")) return "move";
		if (c.matches("vcnt|vclz|vcls")) return "count";
		return "other(" + c + ")";
	}

	// Best effort: walk back up to 24 instructions in the same function looking for a string reference
	// (thread/object name, r0 or r1) and a Thumb function pointer (entry, r1/r2).
	String[] nearbyArgs(Address site) {
		String str = "", entry = "";
		Instruction in = listing.getInstructionAt(site);
		for (int i = 0; i < 24 && in != null; i++) {
			in = in.getPrevious();
			if (in == null) break;
			for (Reference ref : in.getReferencesFrom()) {
				Address t = ref.getToAddress();
				Data d = listing.getDataAt(t);
				if (d != null && d.isPointer() && d.getValue() instanceof Address) {
					Address p = (Address) d.getValue();
					Data pd = listing.getDataAt(p);
					if (pd != null && pd.hasStringValue() && str.isEmpty()) str = String.valueOf(pd.getValue());
					Function pf = fm.getFunctionAt(p);
					if (pf != null && entry.isEmpty()) entry = pf.getName();
				}
				if (d != null && d.hasStringValue() && str.isEmpty()) str = String.valueOf(d.getValue());
				else if (str.isEmpty() && d == null) {
					String c = cstr(t);
					if (c != null) str = c;
				}
				Function tf = fm.getFunctionAt(t);
				if (tf != null && entry.isEmpty() && !ref.getReferenceType().isFlow()) entry = tf.getName();
			}
			if (!str.isEmpty() && !entry.isEmpty()) break;
		}
		return new String[] { str, entry };
	}

	String cstr(Address a) {
		try {
			byte[] buf = new byte[48];
			int n = currentProgram.getMemory().getBytes(a, buf);
			StringBuilder sb = new StringBuilder();
			for (int i = 0; i < n; i++) {
				if (buf[i] == 0) return sb.length() >= 3 ? sb.toString() : null;
				if (buf[i] < 0x20 || buf[i] > 0x7e) return null;
				sb.append((char) buf[i]);
			}
			return sb.length() >= 3 ? sb + "..." : null;
		} catch (Exception e) {
			return null;
		}
	}

	void dump(String title, Map<String, Long> m) {
		log.println("\n## " + title);
		for (Map.Entry<String, Long> e : m.entrySet()) log.printf("  %-60s %d%n", e.getKey(), e.getValue());
	}

	void dumpInline(String title, Map<String, Long> m) {
		List<Map.Entry<String, Long>> l = new ArrayList<>(m.entrySet());
		l.sort((x, y) -> Long.compare(y.getValue(), x.getValue()));
		log.print(title + ":");
		for (int i = 0; i < Math.min(15, l.size()); i++) log.print(" " + l.get(i).getKey() + "=" + l.get(i).getValue());
		log.println();
	}
}
