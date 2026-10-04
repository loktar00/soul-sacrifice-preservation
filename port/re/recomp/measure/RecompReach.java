// Static direct-call reachability from module_start (plus thread entry functions passed to
// sceKernelCreateThread), to scope the "first frame" milestone. Read-only. Writes out/reach.txt.
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.*;
import java.io.*;
import java.util.*;

public class RecompReach extends GhidraScript {
	FunctionManager fm;
	ReferenceManager rm;
	Map<Address, String> importNames = new HashMap<>();

	@Override
	public void run() throws Exception {
		fm = currentProgram.getFunctionManager();
		rm = currentProgram.getReferenceManager();
		try (BufferedReader r = new BufferedReader(new FileReader("E:/soul sacrifice/port/re/ghidra/imports.csv"))) {
			r.readLine();
			for (String line; (line = r.readLine()) != null;) {
				String[] f = line.split(",", -1);
				importNames.put(toAddr(Long.parseLong(f[3], 16)), f[2]);
			}
		}
		PrintWriter w = new PrintWriter(new File("E:/soul sacrifice/port/re/recomp/measure/out/reach.txt"), "UTF-8");
		Address start = toAddr(0x817C7160L);
		Map<Address, Address> parent = new LinkedHashMap<>();
		Deque<Address> q = new ArrayDeque<>();
		parent.put(start, null);
		q.add(start);
		Set<String> importsUsed = new TreeSet<>();
		while (!q.isEmpty()) {
			Function f = fm.getFunctionAt(q.poll());
			if (f == null) continue;
			for (Function c : calleesAndThreadEntries(f)) {
				Address e = c.getEntryPoint();
				if (importNames.containsKey(e)) { importsUsed.add(importNames.get(e)); continue; }
				if (parent.containsKey(e)) continue;
				parent.put(e, f.getEntryPoint());
				q.add(e);
			}
		}
		w.printf("functions reachable from module_start by direct calls (+ thread entries): %d%n", parent.size());
		w.printf("distinct imports called from that set: %d%n  %s%n", importsUsed.size(), importsUsed);
		for (String target : new String[] { "sceDisplaySetFrameBuf", "sceGxmInitialize", "sceGxmCreateContext",
				"sceGxmDisplayQueueAddEntry", "sceKernelCreateThread" }) {
			for (Map.Entry<Address, String> e : importNames.entrySet()) {
				if (!e.getValue().equals(target)) continue;
				for (Reference ref : rm.getReferencesTo(e.getKey())) {
					Function caller = fm.getFunctionContaining(ref.getFromAddress());
					if (caller == null) continue;
					w.printf("%n%s called from %s (%s); reachable=%b; xrefs to caller: %d%n", target, caller.getName(),
							ref.getFromAddress(), parent.containsKey(caller.getEntryPoint()),
							rm.getReferenceCountTo(caller.getEntryPoint()));
					List<String> chain = new ArrayList<>();
					for (Address a = caller.getEntryPoint(); a != null && parent.containsKey(a); a = parent.get(a))
						chain.add(fm.getFunctionAt(a).getName());
					if (parent.containsKey(caller.getEntryPoint())) w.println("  chain (callee <- caller): " + chain);
				}
			}
		}
		w.close();
	}

	List<Function> calleesAndThreadEntries(Function f) {
		List<Function> out = new ArrayList<>();
		InstructionIterator it = currentProgram.getListing().getInstructions(f.getBody(), true);
		while (it.hasNext()) {
			Instruction in = it.next();
			for (Reference ref : in.getReferencesFrom()) {
				RefType t = ref.getReferenceType();
				Function c = fm.getFunctionAt(ref.getToAddress());
				if (c == null) continue;
				// direct/resolved calls and tail jumps, plus address-of-function data refs (thread entries, callbacks)
				if (t.isCall() || (t.isJump() && !c.equals(f)) || (t.isData() && !importNames.containsKey(c.getEntryPoint())))
					out.add(c);
			}
		}
		return out;
	}
}
