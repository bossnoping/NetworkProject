@echo off
pushd "%~dp0.."
call .venv\Scripts\python server\srmp_server.py %*
popd
