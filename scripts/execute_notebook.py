"""Verify and capture Python notebook cells in-process without a network kernel.

This is an execution check for this Python-only teaching notebook. Interactive
Jupyter kernel startup is a separate environment concern.
"""
from pathlib import Path
import os
import nbformat
from IPython.core.interactiveshell import InteractiveShell
from IPython.utils.capture import capture_output

root=Path(__file__).resolve().parents[1]
os.chdir(root)
path=root/'notebooks/Gaia_Stellar_Streams.ipynb'
nb=nbformat.read(path,as_version=4)
shell=InteractiveShell.instance()
count=0
for cell in nb.cells:
 if cell.cell_type!='code': continue
 count+=1
 with capture_output(stdout=True,stderr=True,display=True) as captured:
  result=shell.run_cell(cell.source,store_history=True)
 if result.error_before_exec or result.error_in_exec:
  raise RuntimeError(f'Notebook cell {count} failed') from (result.error_before_exec or result.error_in_exec)
 cell.execution_count=count
 cell.outputs=[]
 if captured.stdout: cell.outputs.append(nbformat.v4.new_output('stream',name='stdout',text=captured.stdout))
 if captured.stderr: cell.outputs.append(nbformat.v4.new_output('stream',name='stderr',text=captured.stderr))
 for rich in captured.outputs:
  cell.outputs.append(nbformat.v4.new_output('display_data',data=rich.data,metadata=rich.metadata))
nb.metadata['verification']={'method':'Python cells executed in-process with IPython; no network kernel', 'executed_code_cells':count}
nbformat.validate(nb)
nbformat.write(nb,path)
print(f'{count} code cells executed successfully; outputs saved')
