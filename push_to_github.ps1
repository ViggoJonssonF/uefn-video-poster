Set-Location "$PSScriptRoot"

git init
git add .
git commit -m "Initial commit - UEFN Video Poster web app"
git branch -M main
git remote add origin https://github.com/ViggoJonssonF/uefn-video-poster.git
git push -u origin main

Write-Host ""
Write-Host "Done! Press any key to close."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
