@echo off
setlocal
if not defined CONDA_PREFIX if not defined VIRTUAL_ENV (
 echo Activate your project environment in Anaconda Prompt first.
 echo Then run: python install.py
 exit /b 2
)
python "%~dp0install.py" %*
set "RESULT=%ERRORLEVEL%"
endlocal & exit /b %RESULT%
