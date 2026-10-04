@echo off
REM Production launcher for the KCRR web UI.
REM
REM Dev mode was `npm run dev` (vite dev server). This builds the static
REM bundle once on startup, then serves it with `vite preview` on the SAME
REM port (5173) so existing access URLs and the QQ login link keep working.
REM
REM NOTE: keep this file pure ASCII -- it is uploaded over SFTP as UTF-8
REM but cmd.exe reads .bat as the OEM codepage (GBK), so non-ASCII bytes
REM corrupt the line parsing.
cd /d "%~dp0"

echo [1/2] Building production bundle ...
call npm run build
if errorlevel 1 (
    echo.
    echo [WARN] Build FAILED. Falling back to the existing dist folder,
    echo        which may be stale. Check the log above.
    echo.
)

echo [2/2] Starting production server on port 5173 ...
call npm run preview
