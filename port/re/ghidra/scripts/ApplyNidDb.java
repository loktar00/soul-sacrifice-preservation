// Re-runs VitaLoaderRedux's NIDAnalyzer on the analyzed program using the DB in VLR_DATABASE_PATH.
import ghidra.app.script.GhidraScript;
import ghidra.app.util.importer.MessageLog;
import vitaloaderredux.analyzer.NIDAnalyzer;

public class ApplyNidDb extends GhidraScript {
	@Override
	public void run() throws Exception {
		println("VLR_DATABASE_PATH=" + System.getenv("VLR_DATABASE_PATH"));
		NIDAnalyzer a = new NIDAnalyzer();
		MessageLog log = new MessageLog();
		int tx = currentProgram.startTransaction("Apply NID DB");
		boolean ok = false;
		try {
			ok = a.added(currentProgram, currentProgram.getMemory(), monitor, log);
		} finally {
			currentProgram.endTransaction(tx, true);
		}
		println("NIDAnalyzer.added -> " + ok);
		println(log.toString());
	}
}
