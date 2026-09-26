@echo off
echo A enviar atualizacoes para o GitHub...
git add .
git commit -m "Atualizacao automatica rapida"
git push origin main
echo Concluido com sucesso!
pause