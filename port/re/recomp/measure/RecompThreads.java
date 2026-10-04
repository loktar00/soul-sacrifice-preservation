// Lists callers of the game's thread-creation wrapper (FUN_817c86da, the only caller of
// sceKernelCreateThread on the main path) with the nearest string literal (thread name). Read-only.
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.*;
import java.io.*;

public class RecompThreads extends GhidraScript {
	@Override
	public void run() throws Exception {
		Listing listing = currentProgram.getListing();
		FunctionManager fm = currentProgram.getFunctionManager();
		Address wrapper = toAddr(0x817c86daL);
		try (PrintWriter w = new PrintWriter(new File("E:/soul sacrifice/port/re/recomp/measure/out/threads.csv"), "UTF-8")) {
			w.println("call_site,ref_type,caller,nearest_string");
			for (Reference ref : currentProgram.getReferenceManager().getReferencesTo(wrapper)) {
				Address site = ref.getFromAddress();
				Function caller = fm.getFunctionContaining(site);
				String str = "";
				Instruction in = listing.getInstructionAt(site);
				for (int i = 0; i < 30 && in != null && str.isEmpty(); i++) {
					in = in.getPrevious();
					if (in == null) break;
					for (Reference r : in.getReferencesFrom()) {
						Data d = listing.getDataAt(r.getToAddress());
						if (d != null && d.hasStringValue()) { str = String.valueOf(d.getValue()); break; }
						if (d == null) {
							byte[] b = new byte[40];
							try {
								int n = currentProgram.getMemory().getBytes(r.getToAddress(), b);
								StringBuilder sb = new StringBuilder();
								for (int k = 0; k < n && b[k] >= 0x20 && b[k] < 0x7f; k++) sb.append((char) b[k]);
								if (sb.length() >= 3) { str = sb.toString(); break; }
							} catch (Exception e) { }
						}
					}
				}
				w.printf("%s,%s,%s,\"%s\"%n", site, ref.getReferenceType(), caller == null ? "" : caller.getName(), str);
			}
		}
	}
}
