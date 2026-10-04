import ghidra.app.script.GhidraScript;
import ghidra.program.model.symbol.*;
import ghidra.program.model.address.*;
public class Dbg extends GhidraScript {
 public void run() throws Exception {
  SymbolTable st=currentProgram.getSymbolTable();
  int n=0;
  for (Symbol s: st.getAllSymbols(true)) { if (s.getName().startsWith("SceLibKernel_")||s.getName().startsWith("SceGxm_")) { Address a=s.getAddress();
    for (Symbol o: st.getSymbols(a)) println("DBG "+o.getName(true)+" @"+a+" "+o.getSource()+" "+o.getSymbolType());
    if(++n>4)break; } }
  for (Symbol s: st.getSymbols("efg")) println("DBG efg "+s.getName(true));
  for (Symbol s: st.getAllSymbols(true)) if (s.getName().startsWith("#")) println("DBG ns "+s.getName(true)+" "+s.getSymbolType());
  println("DBG ext "+currentProgram.getExternalManager().getExternalLibraryNames().length);
 }}
