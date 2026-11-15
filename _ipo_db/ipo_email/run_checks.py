"""Local offline review; never connects to Bloomberg or opens/sends mail."""
import ast
import argparse
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import resource
import sys
import threading
import time
import unittest
import xml.etree.ElementTree as ET
import zipfile


def peak_mib():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024**2 if sys.platform == 'darwin' else 1024)


def watch_memory():
    while True:
        if peak_mib() > 512:
            os._exit(137)
        time.sleep(0.1)


threading.Thread(target=watch_memory, daemon=True).start()
folder = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source-docx', type=Path, help='Optionally recheck the original user-supplied Word attachment.')
args = parser.parse_args()
source_document_unchanged = None
original_source = (folder / 'first_cell_original.py').read_bytes()
assert hashlib.sha256(original_source).hexdigest() == '3865d58796e9b78e0908d7285988deb10a209cb033000fb0af14c8ea0c103aa1'
if args.source_docx:
    expected_hash = '1fe205d3a515acdb92d5bf3841d79b7f6df0e018a0fa2015aab27e62cbf01b02'
    assert hashlib.sha256(args.source_docx.read_bytes()).hexdigest() == expected_hash
    with zipfile.ZipFile(args.source_docx) as document:
        root = ET.fromstring(document.read('word/document.xml'))
    paragraphs = []
    for paragraph in root.findall('.//w:body/w:p', {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}):
        paragraphs.append(''.join((node.text or '') if node.tag.endswith('}t')
                                  else '\n' if node.tag.endswith(('}br', '}cr'))
                                  else '\t' if node.tag.endswith('}tab') else '' for node in paragraph.iter()))
    assert '\n'.join(paragraphs) == original_source.decode('utf-8')
    source_document_unchanged = True
notebook = json.loads((folder / 'HK_IPO_Two_Emails.ipynb').read_text(encoding='utf-8'))
assert notebook['nbformat'] == 4 and notebook['nbformat_minor'] == 5
assert len(notebook['cells']) == 2
for cell, filename in zip(notebook['cells'], ['first_cell_original.py', 'second_cell.py']):
    source = (folder / filename).read_text(encoding='utf-8')
    assert cell['cell_type'] == 'code' and cell['outputs'] == [] and cell['execution_count'] is None
    assert ''.join(cell['source']) == source
    ast.parse(source, feature_version=(3, 8))
    compile(source, filename, 'exec')
suite = unittest.defaultTestLoader.discover(str(folder), pattern='test*.py')
with (folder / 'test_results.txt').open('w', encoding='utf-8') as stream, \
     contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(stream):
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
summary = {'run': result.testsRun, 'failures': len(result.failures), 'errors': len(result.errors),
           'peak_rss_mib': round(peak_mib(), 1), 'python_rss_guard_mib': 512,
           'source_document_unchanged': source_document_unchanged, 'notebook_cells_match_sources': True,
           'python_38_syntax_pass': True, 'live_bloomberg_tested': False, 'live_outlook_tested': False}
(folder / 'review_checks.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
print(json.dumps(summary, indent=2))
assert result.wasSuccessful() and peak_mib() <= 512
