@echo off
echo  This will configure Python for VSCode to have the dependencies that mod-loader needs to run and build.
Echo  This may screw up dependencies that other projects need.
echo  Only continue if you know what you're doing.
pause

python -m pip install pip==19.3.1
pip install cx_Freeze
pip install -r requirements.txt
REM python ./setup.py