@echo off
rem This script helps users get a Python environment installed that can run this
rem application. Experienced users might choose an already existing Python
rem environment to run the application.

echo Checking if conda present...
call conda --version
if errorlevel 1 (
    echo.
    echo To use this launcher, you need to have the conda executable on your path.
    echo If you want to do this, install Miniconda from https://docs.conda.io/en/latest/miniconda.html
    start https://docs.conda.io/en/latest/miniconda.html
    exit /b %errorlevel%
)

echo Checking if python environment present...
call conda activate pyzephyr
if errorlevel 1 (
   echo.
   echo Creating conda environment on first-time use...
   call conda env create -n pyzephyr -f conda-environment.yml
)

echo Launching application...
call conda activate pyzephyr && python main.py %*
