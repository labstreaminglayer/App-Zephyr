#!/bin/bash
# This script helps users get a Python environment installed that can run this
# application. Experienced users might choose an already existing Python
# environment to run the application.

echo "Checking if conda present..."
if ! conda --version &> /dev/null
then
    echo ""
    echo "To use this launcher, you need to have the conda executable on your path."
    echo "If you want to do this, install Miniconda from https://docs.conda.io/en/latest/miniconda.html"
    echo ""
    exit 1
fi

echo "Checking if python environment present..."
source activate pyzephyr &> /dev/null
if [ $? -eq 1 ]; then
   echo ""
   echo "Creating conda environment on first-time use..."
   conda env create -n pyzephyr -f conda-environment.yml
fi

conda activate pyzephyr && python main.py $@
