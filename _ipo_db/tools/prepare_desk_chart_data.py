"""Rebuild derived monitor data with the production update module."""
import runpy,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/"ipo_lib"))
runpy.run_module("prepare_monitor_data",run_name="__main__")
