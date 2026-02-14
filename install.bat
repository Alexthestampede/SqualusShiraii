@echo off
setlocal enabledelayedexpansion

REM Navigate to script directory
cd /d "%~dp0"

echo === Squalus Shiraii Installer ===
echo.

REM ==================== Check system dependencies ====================
where ffmpeg >nul 2>&1
if !ERRORLEVEL! NEQ 0 (
    echo ERROR: ffmpeg is required but not found.
    echo   Install with: winget install ffmpeg
    exit /b 1
)

where git >nul 2>&1
if !ERRORLEVEL! NEQ 0 (
    echo ERROR: git is required but not found.
    echo   Install with: winget install Git.Git
    exit /b 1
)

REM ==================== Find Python 3.11 ====================
REM ACE-Step requires Python 3.11 exactly.
REM Try the Windows Python Launcher first (most reliable), then fall back.
set "PYTHON="

REM Try py -3.11 (Windows Python Launcher)
py -3.11 --version >nul 2>&1
if !ERRORLEVEL! EQU 0 (
    set "PYTHON=py -3.11"
    goto :python_found
)

REM Try python3.11
where python3.11 >nul 2>&1
if !ERRORLEVEL! EQU 0 (
    set "PYTHON=python3.11"
    goto :python_found
)

REM Try python and check version
where python >nul 2>&1
if !ERRORLEVEL! EQU 0 (
    for /f "tokens=*" %%v in ('python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2^>nul') do (
        if "%%v"=="3.11" (
            set "PYTHON=python"
            goto :python_found
        )
    )
)

echo.
echo ERROR: Python 3.11 is required ^(ACE-Step is pinned to ==3.11.*^).
echo.
echo Install Python 3.11 with:
echo   winget install Python.Python.3.11
echo.
echo Then re-run this script.
exit /b 1

:python_found
for /f "tokens=*" %%v in ('!PYTHON! -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')" 2^>nul') do set "PY_VERSION=%%v"
echo Using Python: !PYTHON! ^(!PY_VERSION!^)

REM ==================== Create / verify venv ====================
if not exist ".venv\Scripts\activate.bat" (
    echo Creating virtual environment with Python 3.11...
    !PYTHON! -m venv .venv
) else (
    REM Verify existing venv is 3.11
    for /f "tokens=*" %%v in ('.venv\Scripts\python.exe -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2^>nul') do set "VENV_PY=%%v"
    if not "!VENV_PY!"=="3.11" (
        echo Existing venv is Python !VENV_PY!, need 3.11. Recreating...
        rmdir /s /q .venv
        !PYTHON! -m venv .venv
    )
)

call .venv\Scripts\activate.bat

REM ==================== Upgrade pip ====================
pip install --upgrade pip

REM ==================== Detect GPU and install PyTorch ====================
echo Detecting GPU...
set "IS_NVIDIA=0"
set "IS_ROCM=0"

where nvidia-smi >nul 2>&1
if !ERRORLEVEL! EQU 0 (
    set "IS_NVIDIA=1"
    echo NVIDIA detected - installing PyTorch for CUDA
    pip install torch torchaudio torchvision --index-url https://download.pytorch.org/whl/cu128
    goto :pytorch_done
)

if defined HIP_PATH (
    set "IS_ROCM=1"
    echo AMD ROCm detected ^(HIP_PATH=%HIP_PATH%^)
    echo WARNING: ROCm on Windows requires manual PyTorch setup from AMD's pip index.
    echo   See: https://rocm.docs.amd.com/en/latest/how-to/pytorch-install/pytorch-install.html
    echo Installing CPU PyTorch as safe default...
    pip install torch torchaudio torchvision --index-url https://download.pytorch.org/whl/cpu
    goto :pytorch_done
)

echo No GPU detected - installing CPU PyTorch
pip install torch torchaudio torchvision --index-url https://download.pytorch.org/whl/cpu

:pytorch_done

REM ==================== nano-vllm ====================
set "NANO_VLLM=%~dp0ACE-Step-1.5\acestep\third_parts\nano-vllm"
if exist "!NANO_VLLM!\*" (
    echo Installing nano-vllm...
    if !IS_NVIDIA! EQU 0 (
        REM Non-NVIDIA: flash-attn wheels are CUDA-only. Skip it - SDPA fallback works.
        pip install --no-deps -e "!NANO_VLLM!"
        pip install xxhash transformers
    ) else (
        pip install -e "!NANO_VLLM!"
    )
) else (
    echo WARNING: nano-vllm not found ^(ACE-Step-1.5 submodule missing?^). Skipping.
)

REM ==================== ACE-Step ====================
call :install_submodule "ACE-Step-1.5" pip install --no-deps -e "%~dp0ACE-Step-1.5"

REM ACE-Step runtime deps (minus torch/nano-vllm, already installed)
echo Installing ACE-Step dependencies...
pip install ^
    "transformers>=4.51.0,<4.58.0" ^
    diffusers ^
    "gradio==6.2.0" ^
    "matplotlib>=3.7.5" ^
    "scipy>=1.10.1" ^
    "soundfile>=0.13.1" ^
    "loguru>=0.7.3" ^
    "einops>=0.8.1" ^
    "accelerate>=1.12.0" ^
    "fastapi>=0.110.0" ^
    diskcache ^
    "uvicorn[standard]>=0.27.0" ^
    "numba>=0.63.1" ^
    "vector-quantize-pytorch>=1.27.15" ^
    "torchcodec>=0.9.1" ^
    "torchao>=0.14.1,<0.16.0" ^
    toml ^
    "peft>=0.18.0" ^
    lycoris-lora ^
    "lightning>=2.0.0" ^
    "tensorboard>=2.20.0" ^
    modelscope ^
    "typer-slim>=0.21.1"

REM ==================== Support libraries ====================
echo Installing remaining support libraries...
call :install_submodule "ModuLLe" pip install -e "%~dp0ModuLLe"
call :install_submodule "Qwen3-TTS" pip install -e "%~dp0Qwen3-TTS"

REM DTgRPCconnector is not a pip package - imported at runtime via sys.path.
echo Installing DTgRPCconnector dependencies...
pip install grpcio flatbuffers Pillow

REM ==================== App requirements ====================
echo Installing app requirements...
pip install -r "%~dp0requirements.txt"

REM ==================== Non-NVIDIA cleanup ====================
if !IS_NVIDIA! EQU 0 (
    echo Removing CUDA-only flash-attn ^(SDPA fallback will be used^)...
    pip uninstall -y flash-attn >nul 2>&1
)

REM ==================== ACE-Step model download ====================
echo Downloading ACE-Step models...
where acestep-download >nul 2>&1
if !ERRORLEVEL! EQU 0 (
    acestep-download
) else (
    echo WARNING: acestep-download not found, skip model download. Run manually later.
)

REM ==================== Create data directories ====================
echo Creating data directories...
if not exist "%~dp0data\audio" mkdir "%~dp0data\audio"
if not exist "%~dp0data\art" mkdir "%~dp0data\art"
if not exist "%~dp0data\portraits" mkdir "%~dp0data\portraits"
if not exist "%~dp0data\voices" mkdir "%~dp0data\voices"
if not exist "%~dp0data\exports" mkdir "%~dp0data\exports"

REM ==================== Copy presets ====================
echo Copying presets...
if not exist "%~dp0presets" mkdir "%~dp0presets"
if exist "%~dp0samples\DTpresets\*.json" (
    copy /y "%~dp0samples\DTpresets\*.json" "%~dp0presets\" >nul 2>&1
)

echo.
echo === Installation complete ===
echo Run: run.bat
endlocal
exit /b 0

REM ==================== Helper: install submodule ====================
:install_submodule
REM Usage: call :install_submodule "name" command args...
set "SUB_NAME=%~1"
shift
if exist "%~dp0!SUB_NAME!\*" (
    echo Installing !SUB_NAME!...
    %1 %2 %3 %4 %5 %6 %7 %8 %9
) else (
    echo WARNING: !SUB_NAME! not found or empty. Skipping.
    echo   Run: git submodule update --init !SUB_NAME!
)
exit /b 0
