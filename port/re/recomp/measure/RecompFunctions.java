// Exports every non-external function (entry, Thumb mode, body size, name) to out/functions.csv
// so exidx.py can compare Ghidra's function starts with the EHABI table. Read-only.
import ghidra.app.script.GhidraScript;
import ghidra.program.model.lang.Register;
import ghidra.program.model.listing.*;
import java.io.*;
import java.math.BigInteger;

public class RecompFunctions extends GhidraScript {
	@Override
	public void run() throws Exception {
		Register tmode = currentProgram.getProgramContext().getRegister("TMode");
		try (PrintWriter w = new PrintWriter(new File("E:/soul sacrifice/port/re/recomp/measure/out/functions.csv"), "UTF-8")) {
			w.println("entry,thumb,size,name");
			for (Function f : currentProgram.getFunctionManager().getFunctions(true)) {
				if (f.isExternal()) continue;
				BigInteger v = currentProgram.getProgramContext().getValue(tmode, f.getEntryPoint(), false);
				w.printf("%s,%d,%d,%s%n", f.getEntryPoint(), v == null ? -1 : v.intValue(),
						f.getBody().getNumAddresses(), f.getName());
			}
		}
	}
}
