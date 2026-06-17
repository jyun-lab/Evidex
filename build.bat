@echo off
rem Evidex build script. ASCII + CRLF only.
rem Detection runs the interpreter for real, because 'where' is fooled
rem by the Microsoft Store python stub (documented landmine).

py -3 -c "import sys" >nul 2>nul
if not errorlevel 1 goto USE_PY

python -c "import sys" >nul 2>nul
if not errorlevel 1 goto USE_PYTHON

echo [ERROR] Python 3 was not found (or only the Microsoft Store stub).
echo Install Python 3 from https://www.python.org/ and run this again.
goto END

:USE_PY
py -3 build.py
goto END

:USE_PYTHON
python build.py

:END
echo.
pause

