"""Refresh CSI 300 and rederive dated A/H reference windows."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/"ipo_lib"))
from prepare_ah_reference import main
if __name__=="__main__":main()
