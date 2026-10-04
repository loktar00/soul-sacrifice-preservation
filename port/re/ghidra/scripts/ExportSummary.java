// Writes imports.csv and summary.md next to the project. Headless: -postScript ExportSummary.java
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.*;
import ghidra.program.model.data.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.*;
import java.io.*;
import java.util.*;
import java.util.regex.*;

public class ExportSummary extends GhidraScript {
	static final Pattern SYS = Pattern.compile("^([A-Za-z0-9]+)_([0-9A-F]{8})$");

	@Override
	public void run() throws Exception {
		File outDir = new File("E:/soul sacrifice/port/re/ghidra");
		SymbolTable st = currentProgram.getSymbolTable();
		FunctionManager fm = currentProgram.getFunctionManager();

		// import rows: library, nid, resolved name, address
		TreeMap<Long, String[]> rows = new TreeMap<>();
		Map<String, int[]> perLib = new TreeMap<>(); // [resolved, unresolved]
		for (Symbol s : st.getAllSymbols(true)) {
			if (s.isExternalEntryPoint() && false) continue;
			Matcher m = SYS.matcher(s.getName());
			if (!m.matches() || !m.group(1).startsWith("Sce") || !s.getAddress().isMemoryAddress()) continue;
			Address a = s.getAddress();
			String lib = m.group(1), nid = m.group(2);
			String resolved = "";
			for (Symbol o : st.getSymbols(a)) {
				String n = o.getName();
				if (o == s || SYS.matcher(n).matches() || n.startsWith("FUN_") || n.startsWith("LAB_")
						|| n.startsWith("DAT_") || n.startsWith("thunk_FUN_") || n.startsWith("PTR_")) continue;
				resolved = n;
				break;
			}
			String stub = a.toString();
			String kind = "import";
			if (a.isExternalAddress()) {
				ghidra.program.model.symbol.Reference[] refs = getReferencesTo(a);
				if (refs.length > 0) stub = refs[0].getFromAddress().toString();
			}
			rows.put((long) rows.size(), new String[] { lib, nid, resolved, stub, kind });
		}
		try (PrintWriter w = new PrintWriter(new File(outDir, "imports.csv"))) {
			w.println("library,nid,resolved_name,stub_address,kind");
			for (String[] r : rows.values()) {
				w.println(r[0] + ",0x" + r[1] + "," + r[2] + "," + r[3] + "," + r[4]);
				if (!r[4].equals("import")) continue;
				int[] c = perLib.computeIfAbsent(r[0], k -> new int[2]);
				c[r[2].isEmpty() ? 1 : 0]++;
			}
		}

		// module info
		StringBuilder mi = new StringBuilder();
		Address miAddr = null;
		for (Symbol s : st.getSymbols("__sce_moduleinfo")) miAddr = s.getAddress();
		if (miAddr != null) {
			Data d = currentProgram.getListing().getDataAt(miAddr);
			mi.append("- `__sce_moduleinfo` at ").append(miAddr).append("\n");
			Data cm = d.getComponent(0);
			for (int i = 0; cm != null && i < cm.getNumComponents(); i++) {
				Data c = cm.getComponent(i);
				mi.append("  - common." + c.getFieldName()).append(" = ").append(c.getDefaultValueRepresentation()).append("\n");
			}
			for (Namespace ns = st.getPrimarySymbol(miAddr).getParentNamespace(); ns != null && !ns.isGlobal(); ns = ns.getParentNamespace())
				mi.append("  - namespace: ").append(ns.getName()).append("\n");
			for (int i = 0; i < d.getNumComponents(); i++) {
				Data c = d.getComponent(i);
				mi.append("  - ").append(c.getFieldName()).append(" = ").append(c.getDefaultValueRepresentation())
						.append(" (").append(c.getDataType().getName()).append(")\n");
			}
		} else mi.append("- no `__sce_moduleinfo` symbol found (non-VLR load)\n");

		// entry points
		StringBuilder ep = new StringBuilder();
		for (Address a : st.getExternalEntryPointIterator()) {
			Symbol p = st.getPrimarySymbol(a);
			ep.append("- ").append(a).append(" ").append(p == null ? "" : p.getName(true)).append("\n");
		}

		// largest functions
		List<Function> fl = new ArrayList<>();
		for (Function f : fm.getFunctions(true)) fl.add(f);
		fl.sort((x, y) -> Long.compare(y.getBody().getNumAddresses(), x.getBody().getNumAddresses()));

		int tot = 0, res = 0;
		StringBuilder pl = new StringBuilder("| library | resolved | unresolved |\n|---|---|---|\n");
		for (Map.Entry<String, int[]> e : perLib.entrySet()) {
			pl.append("| ").append(e.getKey()).append(" | ").append(e.getValue()[0]).append(" | ").append(e.getValue()[1]).append(" |\n");
			res += e.getValue()[0]; tot += e.getValue()[0] + e.getValue()[1];
		}
		try (PrintWriter w = new PrintWriter(new File(outDir, "summary.md"))) {
			w.println("# eboot.elf Ghidra summary\n");
			w.println("- Program: " + currentProgram.getName() + ", language " + currentProgram.getLanguageID()
					+ ", image base " + currentProgram.getImageBase());
			w.println("- Function count: " + fm.getFunctionCount());
			w.println("- Imported functions (stub entries with systematic Lib_NID names): " + tot + " (resolved " + res + ", unresolved " + (tot - res) + ")\n");
			w.println("## Module info\n" + mi);
			w.println("## Entry points\n" + ep);
			w.println("## Imports per library\n" + pl);
			w.println("## 10 largest functions\n| function | address | size (bytes) |\n|---|---|---|");
			for (int i = 0; i < Math.min(10, fl.size()); i++) {
				Function f = fl.get(i);
				w.println("| " + f.getName() + " | " + f.getEntryPoint() + " | " + f.getBody().getNumAddresses() + " |");
			}
		}
		println("ExportSummary done: " + rows.size() + " stub rows");
	}
}
