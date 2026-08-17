@echo off
REM Wrapper so OrcaSlicer's Post-processing Scripts field can launch this
REM directly on Windows. OrcaSlicer tries to execute whatever path you give
REM it as a program in its own right -- a .py file isn't a valid Windows
REM executable (Win32 error 193 / ERROR_BAD_EXE_FORMAT), but a .bat file is,
REM and this one just forwards to Python.
REM
REM If "python" isn't recognized when this runs (check by opening a terminal
REM and running `python --version`), replace "python" below with the full
REM path to python.exe (find it with `where python`), or with "py".
REM
REM IMPORTANT: this file finds flashforge_gx_post.py via %~dp0, i.e. "the
REM folder this .bat is in" -- keep the two files together. Confirmed by
REM real testing (in the source project this was adapted from): moving/
REM copying just the .bat elsewhere fails with "Error code: 2" (Python's
REM own exit code for "script file not found").
python "%~dp0flashforge_gx_post.py" %*
