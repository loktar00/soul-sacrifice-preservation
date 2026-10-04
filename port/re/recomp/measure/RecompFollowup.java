// Follow-up measurements for RecompMeasure: what resolved indirect calls point at, code layout by region,
// instructions outside functions, bkpt/bad-instruction sites, vtable-like pointer runs. Read-only.
// Writes out/followup.txt.
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.*;
import ghidra.program.model.lang.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.mem.*;
import ghidra.program.model.symbol.*;
import java.io.*;
import java.math.BigInteger;
import java.util.*;

public class RecompFollowup extends GhidraScript {
	static final File OUT = new File("E:/soul sacrifice/port/re/recomp/measure/out");
	PrintWriter log;
	Listing listing;
	FunctionManager fm;
	ReferenceManager rm;

	String ops(Instruction in) {
		StringBuilder sb = new StringBuilder();
		for (int i = 0; i < in.getNumOperands(); i++) {
			if (i > 0) sb.append(',');
			sb.append(in.getDefaultOperandRepresentation(i));
		}
		return sb.toString();
	}

	String ctxLines(Instruction in, int back) {
		Instruction p = in;
		for (int i = 0; i < back && p.getPrevious() != null; i++) p = p.getPrevious();
		StringBuilder sb = new StringBuilder();
		while (p != null && p.getAddress().compareTo(in.getAddress()) <= 0) {
			sb.append("    ").append(p.getAddress()).append("  ").append(p.getMnemonicString()).append(' ')
					.append(ops(p)).append('\n');
			p = p.getNext();
		}
		return sb.toString();
	}

	@Override
	public void run() throws Exception {
		listing = currentProgram.getListing();
		fm = currentProgram.getFunctionManager();
		rm = currentProgram.getReferenceManager();
		Memory mem = currentProgram.getMemory();
		Register tmode = currentProgram.getProgramContext().getRegister("TMode");
		log = new PrintWriter(new File(OUT, "followup.txt"), "UTF-8");
		MemoryBlock text = mem.getBlock(".text");
		AddressSet textSet = new AddressSet(text.getStart(), text.getEnd());

		// stubs: functions in the import-stub area named after imports (contiguous 16-byte stubs)
		Set<Address> stubEntries = new HashSet<>();
		try (BufferedReader r = new BufferedReader(new FileReader("E:/soul sacrifice/port/re/ghidra/imports.csv"))) {
			r.readLine();
			for (String line; (line = r.readLine()) != null;) stubEntries.add(toAddr(Long.parseLong(line.split(",")[3], 16)));
		}

		// 1. computed calls: target categories, and context samples per register
		Map<String, Long> cat = new TreeMap<>();
		Map<String, Integer> samples = new HashMap<>();
		StringBuilder sampleText = new StringBuilder();
		InstructionIterator it = listing.getInstructions(textSet, true);
		long[] hist = new long[256];
		long[] histOut = new long[256];
		long outRuns = 0, outRunsAfterNoret = 0, outRunsRefd = 0, outInstr = 0;
		Map<String, Long> outPrev = new TreeMap<>();
		Set<Long> runStarts = new HashSet<>();
		Map<String, Long> bkptPrev = new TreeMap<>();
		long bkptInFn = 0, bkptOutFn = 0;
		Instruction prevIns = null;
		boolean prevOut = false;
		while (it.hasNext()) {
			Instruction in = it.next();
			Address a = in.getAddress();
			int bucket = (int) ((a.getOffset() - 0x81000000L) >> 16);
			hist[bucket]++;
			Function fn = fm.getFunctionContaining(a);
			boolean out = fn == null;
			if (out) {
				histOut[bucket]++;
				outInstr++;
				boolean contiguous = prevIns != null && prevIns.getMaxAddress().next() != null
						&& prevIns.getMaxAddress().next().equals(a);
				if (!prevOut || !contiguous) {
					outRuns++;
					runStarts.add(a.getOffset());
					if (rm.getReferenceCountTo(a) > 0) outRunsRefd++;
					String pm = prevIns == null || !contiguous ? "(gap)"
							: prevIns.getMnemonicString() + (prevIns.getFlowType().isCall() ? " [call]" : "");
					if (prevIns != null && contiguous && prevIns.getFlowType().isCall()) {
						Address[] fl = prevIns.getFlows();
						Function cf = fl.length == 1 ? fm.getFunctionAt(fl[0]) : null;
						if (cf != null && cf.hasNoReturn()) outRunsAfterNoret++;
					}
					outPrev.merge(pm, 1L, Long::sum);
				}
			}
			String mn = in.getMnemonicString().toLowerCase();
			if (mn.startsWith("bkpt")) {
				if (out) bkptOutFn++; else bkptInFn++;
				Instruction p = in.getPrevious();
				bkptPrev.merge(p == null ? "?" : p.getMnemonicString() + (p.getFlowType().isCall() ? " [call]" : ""), 1L, Long::sum);
			}
			FlowType ft = in.getFlowType();
			if (ft.isComputed() && ft.isCall()) {
				String reg = ops(in);
				String c = "unresolved";
				for (Reference ref : in.getReferencesFrom()) {
					if (!ref.getReferenceType().isFlow()) continue;
					Address t = ref.getToAddress();
					if (stubEntries.contains(t)) c = "import_stub";
					else if (fm.getFunctionAt(t) != null) c = "function_entry";
					else c = "other";
				}
				cat.merge(reg + " -> " + c, 1L, Long::sum);
				String sk = reg + "/" + c;
				if (samples.merge(sk, 1, Integer::sum) <= 2 && (reg.equals("r12") || reg.equals("lr") || reg.equals("r1")))
					sampleText.append("  [").append(sk).append("]\n").append(ctxLines(in, 5));
			}
			prevIns = in;
			prevOut = out;
		}
		log.println("## computed calls by register -> what Ghidra resolved the target to");
		for (Map.Entry<String, Long> e : cat.entrySet()) if (e.getValue() >= 20) log.printf("  %-40s %d%n", e.getKey(), e.getValue());
		log.println("\n## samples");
		log.print(sampleText);

		log.println("\n## instructions per 64 KiB of .text (bucket start, instructions, outside-function)");
		for (int i = 0; i < 256; i++) if (hist[i] > 0 || i % 16 == 0)
			log.printf("  %08x %7d %7d%n", 0x81000000L + ((long) i << 16), hist[i], histOut[i]);

		log.printf("%n## instructions outside functions: %d in %d runs; runs with an xref to their start=%d; " +
				"runs right after a call to a no-return function=%d%n", outInstr, outRuns, outRunsRefd, outRunsAfterNoret);
		List<Map.Entry<String, Long>> l = new ArrayList<>(outPrev.entrySet());
		l.sort((x, y) -> Long.compare(y.getValue(), x.getValue()));
		log.println("  instruction preceding each run (top 15):");
		for (int i = 0; i < Math.min(15, l.size()); i++) log.printf("    %-40s %d%n", l.get(i).getKey(), l.get(i).getValue());

		log.printf("%n## bkpt: in_function=%d outside=%d; preceding instruction (top 10):%n", bkptInFn, bkptOutFn);
		l = new ArrayList<>(bkptPrev.entrySet());
		l.sort((x, y) -> Long.compare(y.getValue(), x.getValue()));
		for (int i = 0; i < Math.min(10, l.size()); i++) log.printf("    %-40s %d%n", l.get(i).getKey(), l.get(i).getValue());

		log.println("\n## bad-instruction bookmarks");
		Iterator<Bookmark> bit = currentProgram.getBookmarkManager().getBookmarksIterator("Error");
		while (bit.hasNext()) {
			Bookmark b = bit.next();
			Function f = fm.getFunctionContaining(b.getAddress());
			log.printf("  %s %s %s fn=%s%n", b.getAddress(), b.getCategory(), b.getComment(), f == null ? "-" : f.getName());
		}

		// outside-function run starts that some aligned data word points at (with the Thumb bit): likely
		// functions Ghidra never created (vtable/callback targets)
		long runStartsPointed = 0;
		Set<Long> seen = new HashSet<>();
		for (MemoryBlock blk : mem.getBlocks()) {
			if (!blk.isInitialized() || blk.getStart().getOffset() < 0x81000000L) continue;
			byte[] buf = new byte[(int) blk.getSize()];
			blk.getBytes(blk.getStart(), buf);
			for (int i = 0; i + 4 <= buf.length; i += 4) {
				long v = (buf[i] & 0xffL) | (buf[i + 1] & 0xffL) << 8 | (buf[i + 2] & 0xffL) << 16 | (buf[i + 3] & 0xffL) << 24;
				if ((v & 1) == 1 && runStarts.contains(v & ~1L) && seen.add(v)) runStartsPointed++;
			}
		}
		log.printf("outside-function run starts pointed to by an aligned data word (|1): %d of %d%n", runStartsPointed, outRuns);

		// 2. vtable-like runs: >=3 consecutive aligned words that are Thumb function entries
		Set<Address> fnEntries = new HashSet<>();
		for (Function f : fm.getFunctions(true)) fnEntries.add(f.getEntryPoint());
		long tables = 0, tableWords = 0, longest = 0;
		Map<String, Long> tablesPerBlock = new TreeMap<>();
		for (MemoryBlock blk : mem.getBlocks()) {
			if (!blk.isInitialized() || blk.getStart().getOffset() < 0x81000000L) continue;
			byte[] buf = new byte[(int) blk.getSize()];
			blk.getBytes(blk.getStart(), buf);
			int run = 0;
			for (int i = 0; i + 4 <= buf.length; i += 4) {
				long v = (buf[i] & 0xffL) | (buf[i + 1] & 0xffL) << 8 | (buf[i + 2] & 0xffL) << 16 | (buf[i + 3] & 0xffL) << 24;
				boolean isFn = v >= 0x81000000L && v < 0x81c4d200L && (v & 1) == 1 && fnEntries.contains(toAddr(v & ~1L))
						&& listing.getInstructionContaining(blk.getStart().add(i)) == null;
				if (isFn) run++;
				if (!isFn || i + 8 > buf.length) {
					if (run >= 3) {
						tables++;
						tableWords += run;
						longest = Math.max(longest, run);
						tablesPerBlock.merge(blk.getName(), 1L, Long::sum);
					}
					run = 0;
				}
			}
		}
		log.printf("%n## vtable-like runs (>=3 consecutive Thumb function pointers): tables=%d words=%d longest=%d per_block=%s%n",
				tables, tableWords, longest, tablesPerBlock);

		// 3. mode of import stubs and ARM-mode functions
		log.println("\n## ARM-mode (TMode=0) functions outside the stub area");
		for (Function f : fm.getFunctions(true)) {
			if (f.isExternal() || stubEntries.contains(f.getEntryPoint())) continue;
			BigInteger v = currentProgram.getProgramContext().getValue(tmode, f.getEntryPoint(), false);
			if (v != null && v.intValue() == 0)
				log.printf("  %s %s size=%d callers=%d%n", f.getEntryPoint(), f.getName(), f.getBody().getNumAddresses(),
						rm.getReferenceCountTo(f.getEntryPoint()));
		}
		int stubArm = 0, stubThumb = 0;
		for (Address s : stubEntries) {
			if (s.getOffset() >= 0xff000000L) continue;
			BigInteger v = currentProgram.getProgramContext().getValue(tmode, s, false);
			if (v != null && v.intValue() == 1) stubThumb++; else stubArm++;
		}
		log.printf("import stubs: arm=%d thumb=%d%n", stubArm, stubThumb);
		Instruction si = listing.getInstructionAt(toAddr(0x81aeada8L));
		if (si != null) log.print("sceKernelCreateThread stub:\n" + ctxLines(si.getNext().getNext().getNext(), 3));
		log.close();
		println("RecompFollowup done");
	}
}
