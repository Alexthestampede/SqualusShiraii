# AGENTS.md — YuE2 on RX 7800 XT workspace

Local runtime for [YuE2-3B](https://huggingface.co/m-a-p/YuE2-3B) music generation on AMD ROCm (Nobara 44, ROCm 7.1.1, RX 7800 XT 16GB, gfx1101). Not a git tree itself: `YuE/` is a cloned upstream repo (editable-installed, with local patches), `webui/` is the local app (mirrored to github.com/Alexthestampede/YuE2UI).

## Environment (do not break)

- Use `.venv/bin/python` (Python 3.12 via uv). Torch is `torch==2.10.0+rocm7.1` from `https://download.pytorch.org/whl/rocm7.1` — never plain-pip-install torch; it silently replaces the ROCm build.
- `export MIOPEN_FIND_MODE=FAST` before any GPU work. Without it, the VAE decode pays a 40–90s per-shape MIOpen JIT search per new tensor shape (kills benchmarks and first jobs).
- GPU sanity check: `rocm-smi --showuse` — GPU use should be ~0% before benchmarking. Generation runs take 3× longer if the user is gaming; do not draw perf conclusions from contaminated runs.

## Local YuE patches (lost on `git pull` in `YuE/`; re-apply from YuE2UI's install.sh, which does this programmatically)

1. `YuE/src/yue2/cuda_graph.py`, `attention_backend == "auto"` branch: on `torch.version.hip` force `"sdpa"`. Upstream picks `"flash"` (rejects `seqused_k` → `RuntimeError: mha_varlen_fwd`) then `"cudnn"` (no kernel: "No available kernel"). Plain SDPA works on HIP, even inside CUDA graph capture.
2. `YuE/src/yue2/pipeline.py`: pass `query_chunk_size=self.nar_query_chunk_size` into the NAR `synthesize()` call. Without it, long songs OOM in NAR prefill (ROCm math-SDPA materializes a full [heads, seq, seq] matrix; 8.4 GiB at ~12k frames). Env knob: `YUE2_NAR_QUERY_CHUNK` (default 1024).
3. Backend selection (webui/server.py only, not a patch): `backend="torch-eager"` on HIP — ~2.1× faster than CUDA-graph execution (semantic AR 7.0 → 22.3 tok/s). NVIDIA keeps graphs.

## Commands

- Start UI: `./webui/../.venv/bin/python webui/server.py` is NOT the pattern — use `.venv/bin/python webui/server.py`. Port 7860; songs to `outputs/webui/<jobid>/`.
- Quick end-to-end verify: POST `/api/generate` with `{style, lyrics, cot:"full", seed}`, poll `/api/jobs/{id}` until `status: done`.
- Backend A/B: `.venv/bin/python bench_backend.py --backend torch|torch-eager --out /tmp/x.flac` (fixed seed+request, prints per-stage tok/s).
- VAE decode paths: `bench_vae_paths.py --latents outputs/webui/<id>/latent.npy`.

## Server mechanics (bash-tool gotchas)

- Backgrounding the server with plain `nohup ... &` hangs the bash session until timeout. Use `(setsid nohup .venv/bin/python webui/server.py > outputs/webui.log 2>&1 < /dev/null &)` then poll with `curl --max-time 5`.
- The webui worker thread keeps the loaded pipeline resident across jobs; restart the server after editing `YuE/src/yue2/*` (editable install) or `webui/server.py`.
- Jobs are in-memory only: killing the server loses queued/running jobs (saved songs persist). One job at a time — a queued job waits for the current one.

## YuE2 model facts that change behavior

- The saved ABC plan **embeds the request seed**. Reusing a plan (`plan_dir`) replays the same take; new style/lyrics typed in the form are *ignored* when `plan_dir` is set. New take with same melody = paste ABC into score box + clear seed.
- 16 NAR ODE steps ("preview") ≈ 32 steps ("full") audibly; preview is the webui default and the honest choice.
- Song length scales with lyric structure (~25 semantic tokens per second of audio); tiny lyrics → ~1 min songs.
- FP8 quantization in `quantization.py` requires NVIDIA cc ≥ 8.9 — dead end on AMD. The VAE is FP32-enforced.
- Timing calibration (idle GPU): 66–84s song e2e ≈ 210s eager; 4-min song ≈ 12 min fresh preview, ≈ 9 min plan-reuse reroll.

## Licenses

YuE2 model weights CC BY-NC 4.0 (non-commercial); YuE code Apache 2.0. The webui code is Apache 2.0.