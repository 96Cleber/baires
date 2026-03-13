C:\Users\Cleber\Downloads\FlowVisionAI-Windows(10)>FlowVisionAI.exe
Traceback (most recent call last):
  File "pyi_rth_multiprocessing.py", line 54, in <module>
  File "pyi_rth_multiprocessing.py", line 16, in _pyi_rthook
  File "C:\Users\Cleber\Downloads\FlowVisionAI-Windows(10)\_internal\torch\multiprocessing\__init__.py", line 21, in <module>
    import torch
  File "<frozen importlib._bootstrap>", line 1176, in _find_and_load
  File "<frozen importlib._bootstrap>", line 1147, in _find_and_load_unlocked
  File "<frozen importlib._bootstrap>", line 690, in _load_unlocked
  File "pyimod02_importers.py", line 457, in exec_module
  File "torch\__init__.py", line 49, in <module>
    from torch._utils_internal import (
  File "<frozen importlib._bootstrap>", line 1176, in _find_and_load
  File "<frozen importlib._bootstrap>", line 1147, in _find_and_load_unlocked
  File "<frozen importlib._bootstrap>", line 690, in _load_unlocked
  File "pyimod02_importers.py", line 457, in exec_module
  File "torch\_utils_internal.py", line 6, in <module>
    import tempfile
  File "<frozen importlib._bootstrap>", line 1176, in _find_and_load
  File "<frozen importlib._bootstrap>", line 1147, in _find_and_load_unlocked
  File "<frozen importlib._bootstrap>", line 690, in _load_unlocked
  File "pyimod02_importers.py", line 457, in exec_module
  File "tempfile.py", line 46, in <module>
  File "<frozen importlib._bootstrap>", line 1176, in _find_and_load
  File "<frozen importlib._bootstrap>", line 1147, in _find_and_load_unlocked
  File "<frozen importlib._bootstrap>", line 690, in _load_unlocked
  File "pyimod02_importers.py", line 457, in exec_module
  File "torch\random.py", line 10, in <module>
    def set_rng_state(new_state: torch.Tensor) -> None:
                                 ^^^^^^^^^^^^
AttributeError: partially initialized module 'torch' has no attribute 'Tensor' (most likely due to a circular import)
[PYI-14860:ERROR] Failed to execute script 'pyi_rth_multiprocessing' due to unhandled exception!

C:\Users\Cleber\Downloads\FlowVisionAI-Windows(10)>