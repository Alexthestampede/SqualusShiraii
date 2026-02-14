@echo off
setlocal enabledelayedexpansion

REM Navigate to script directory
cd /d "%~dp0"

REM ==================== Activate venv ====================
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
) else (
    echo ERROR: .venv not found. Run install.bat first.
    exit /b 1
)

REM ==================== ROCm environment setup ====================
REM Matches ACE-Step's start_api_server_rocm.bat env vars
where nvidia-smi >nul 2>&1
if !ERRORLEVEL! NEQ 0 (
    if defined HIP_PATH (
        echo ROCm detected - configuring AMD GPU environment...

        REM HSA_OVERRIDE_GFX_VERSION: required for consumer RDNA3 GPUs.
        REM Change to 11.0.1 for gfx1101 ^(RX 7700 XT, RX 7800 XT^)
        REM Change to 11.0.2 for gfx1102 ^(RX 7600^)
        if not defined HSA_OVERRIDE_GFX_VERSION (
            set HSA_OVERRIDE_GFX_VERSION=11.0.0
        )

        REM Force PyTorch LM backend - nano-vllm requires CUDA flash-attn
        if not defined ACESTEP_LM_BACKEND set ACESTEP_LM_BACKEND=pt

        REM Disable torch.compile Triton backend (not available on ROCm Windows)
        if not defined TORCH_COMPILE_BACKEND set TORCH_COMPILE_BACKEND=eager

        REM Prevent first-run VAE decode hang (MIOpen exhaustive search)
        if not defined MIOPEN_FIND_MODE set MIOPEN_FIND_MODE=FAST

        REM Avoid HuggingFace tokenizer fork warnings
        if not defined TOKENIZERS_PARALLELISM set TOKENIZERS_PARALLELISM=false

        echo   HSA_OVERRIDE_GFX_VERSION=!HSA_OVERRIDE_GFX_VERSION!
        echo   ACESTEP_LM_BACKEND=!ACESTEP_LM_BACKEND!
        echo   TORCH_COMPILE_BACKEND=!TORCH_COMPILE_BACKEND!
        echo   MIOPEN_FIND_MODE=!MIOPEN_FIND_MODE!
    )
)

REM ==================== Start ACE-Step API ====================
echo Starting ACE-Step API on :8001...
start "SqualusShiraii-ACEStep" /min cmd /c "call .venv\Scripts\activate.bat && acestep-api --host 127.0.0.1 --port 8001"

REM ==================== Health check ====================
echo Waiting for ACE-Step to be ready...
set "RETRIES=0"
:health_loop
if !RETRIES! GEQ 60 (
    echo ERROR: ACE-Step did not become ready after 120 seconds.
    echo Check the ACE-Step window for errors.
    goto :cleanup
)
curl -sf http://127.0.0.1:8001/health >nul 2>&1
if !ERRORLEVEL! EQU 0 (
    echo ACE-Step ready.
    goto :health_done
)
set /a RETRIES+=1
timeout /t 2 /nobreak >nul
goto :health_loop

:health_done

REM ==================== Start Squalus Shiraii ====================
echo.
echo === Squalus Shiraii running ===
echo   App:      http://localhost:8000
echo   ACE-Step: http://localhost:8001
echo.
echo Press Ctrl+C to stop.
echo.

uvicorn app.main:app --host 0.0.0.0 --port 8000

REM ==================== Cleanup ====================
:cleanup
echo.
echo Shutting down...
taskkill /fi "windowtitle eq SqualusShiraii-ACEStep*" /f >nul 2>&1
echo Done.
endlocal
