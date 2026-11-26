"""Kaggle GPU job: Wan 2.2 TI2V-5B image-to-video for the clips listed in jobs.json.

Runs on a Kaggle GPU kernel (pushed by `python -m pipeline video-submit`).
T4/P100 constraints shape this script:
  * The official Wan repo hard-requires FlashAttention 2 (unsupported on these GPUs),
    so we use the Diffusers pipeline, which uses PyTorch SDPA attention.
  * No bf16 on T4/P100: the 5B transformer runs in fp16.
  * The UMT5-XXL text encoder is unstable in fp16, so prompts are encoded ONCE in fp32 on the
    CPU, then the encoder is freed before the transformer is loaded (Kaggle RAM ~29 GB).
Results are written after every clip so a timeout still leaves finished clips behind.
"""

import gc
import glob
import os as _os

_os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
import json
import os
import subprocess
import sys
import time
import traceback

subprocess.run(
    [sys.executable, "-m", "pip", "install", "-q", "-U", "diffusers>=0.35", "transformers>=4.51",
     "accelerate", "ftfy", "imageio", "imageio-ffmpeg"],
    check=False,
)

import numpy as np  # noqa: E402
import torch  # noqa: E402
from diffusers import AutoencoderKLWan, WanImageToVideoPipeline  # noqa: E402
from diffusers.utils import export_to_video  # noqa: E402
from PIL import Image  # noqa: E402
from transformers import AutoTokenizer, UMT5EncoderModel  # noqa: E402

MODEL = "Wan-AI/Wan2.2-TI2V-5B-Diffusers"
OUT = "/kaggle/working"
NEG = (
    "bright saturated colours, overexposed, static, blurry details, subtitles, text, watermark, "
    "low quality, jpeg artifacts, ugly, deformed, extra fingers, poorly drawn hands, poorly drawn face, "
    "disfigured, malformed limbs, fused fingers, messy background, three legs, walking backwards"
)
MAX_SEQ = 512

jobs_file = glob.glob("/kaggle/input/**/jobs.json", recursive=True)[0]
in_dir = os.path.dirname(jobs_file)
jobs = json.load(open(jobs_file))
results = []
gpu_name = torch.cuda.get_device_name(0)
print(f"{len(jobs)} job(s) on {gpu_name} x{torch.cuda.device_count()}", flush=True)


def save_results():
    with open(os.path.join(OUT, "results.json"), "w") as f:
        json.dump(results, f, indent=2)


# ---- 1. encode every prompt once with the fp32 text encoder on CPU ----
t0 = time.time()
tok = AutoTokenizer.from_pretrained(MODEL, subfolder="tokenizer")
te = UMT5EncoderModel.from_pretrained(MODEL, subfolder="text_encoder", torch_dtype=torch.float32)
te.eval()


@torch.no_grad()
def encode(text):
    t = tok([text], padding="max_length", max_length=MAX_SEQ, truncation=True,
            add_special_tokens=True, return_attention_mask=True, return_tensors="pt")
    seq_len = int(t.attention_mask.gt(0).sum())
    h = te(t.input_ids, t.attention_mask).last_hidden_state[0, :seq_len]
    return torch.cat([h, h.new_zeros(MAX_SEQ - seq_len, h.size(1))])[None]


neg_emb = encode(NEG)
embeds = {j["key"]: encode(j["prompt"]) for j in jobs}
del te
gc.collect()
print(f"prompts encoded in {time.time() - t0:.0f}s", flush=True)

# ---- 2. load the fp16 transformer + fp32 VAE on GPU 0 ----
vae = AutoencoderKLWan.from_pretrained(MODEL, subfolder="vae", torch_dtype=torch.float32)
pipe = WanImageToVideoPipeline.from_pretrained(
    MODEL, vae=vae, text_encoder=None, tokenizer=None, torch_dtype=torch.float16
)
DEVICE = torch.device("cuda:0")
# Attempt 1 OOMed on a 15 GB T4 (fp16 weights ~10 GB + activations). Store the transformer weights in
# fp8 and upcast each layer to fp16 just for compute: ~5 GB of weights, same maths precision.
STORAGE = "fp16"
try:
    pipe.transformer.enable_layerwise_casting(
        storage_dtype=torch.float8_e4m3fn, compute_dtype=torch.float16
    )
    STORAGE = "fp8-storage/fp16-compute"
except Exception as exc:  # noqa: BLE001
    print("layerwise casting unavailable:", exc, flush=True)
pipe.transformer.to(DEVICE)
type(pipe)._execution_device = property(lambda self: DEVICE)
# The VAE decodes on the second T4 when there is one (Kaggle gives T4 x2).
VAE_DEVICE = torch.device("cuda:1") if torch.cuda.device_count() > 1 else DEVICE
pipe.vae.to(VAE_DEVICE)
try:
    pipe.vae.enable_tiling()
except Exception:  # noqa: BLE001
    pass


@torch.no_grad()
def decode(latents):
    """Same maths as WanImageToVideoPipeline's decode, but on VAE_DEVICE."""
    vae = pipe.vae
    latents = latents.to(VAE_DEVICE, vae.dtype)
    mean = torch.tensor(vae.config.latents_mean).view(1, vae.config.z_dim, 1, 1, 1)
    std = 1.0 / torch.tensor(vae.config.latents_std).view(1, vae.config.z_dim, 1, 1, 1)
    latents = latents / std.to(latents) + mean.to(latents)
    video = vae.decode(latents, return_dict=False)[0]
    return pipe.video_processor.postprocess_video(video, output_type="np")[0]


def centre_crop(img, w, h):
    iw, ih = img.size
    scale = max(w / iw, h / ih)
    img = img.resize((round(iw * scale), round(ih * scale)), Image.LANCZOS)
    left, top = (img.width - w) // 2, (img.height - h) // 2
    return img.crop((left, top, left + w, top + h))


# ---- 3. one clip per job ----
for job in jobs:
    t1 = time.time()
    for d in range(torch.cuda.device_count()):
        torch.cuda.reset_peak_memory_stats(d)
    rec = {**job, "gpu": f"{gpu_name} x{torch.cuda.device_count()}",
           "dtype": f"transformer {STORAGE} / fp32 vae on {VAE_DEVICE} / fp32 text-encoder (cpu)"}
    try:
        img = centre_crop(Image.open(os.path.join(in_dir, job["image"])).convert("RGB"),
                          job["width"], job["height"])
        latents = pipe(
            image=img,
            prompt_embeds=embeds[job["key"]].to(DEVICE, torch.float16),
            negative_prompt_embeds=neg_emb.to(DEVICE, torch.float16),
            height=job["height"],
            width=job["width"],
            num_frames=job["frames"],
            num_inference_steps=job["steps"],
            guidance_scale=5.0,
            generator=torch.Generator("cpu").manual_seed(int(job["seed"])),
            output_type="latent",
        ).frames
        torch.cuda.empty_cache()
        frames = decode(latents)
        arr = np.asarray(frames, dtype=np.float32)
        if not np.isfinite(arr).all() or arr.mean() < 0.01:
            raise RuntimeError(f"degenerate output (mean={np.nanmean(arr):.4f}); likely fp16 overflow")
        fname = f"{job['shot']}_{job['key']}.mp4"
        export_to_video(frames, os.path.join(OUT, fname), fps=job["fps"])
        rec.update(status="ok", file=fname)
    except Exception as exc:  # noqa: BLE001
        rec.update(status="error", error=f"{type(exc).__name__}: {exc}"[:800])
        traceback.print_exc()
    rec["gpu_s"] = round(time.time() - t1, 1)
    rec["peak_vram_gb"] = round(torch.cuda.max_memory_allocated(DEVICE) / 1e9, 2)
    rec["peak_vram_vae_gb"] = round(torch.cuda.max_memory_allocated(VAE_DEVICE) / 1e9, 2)
    results.append(rec)
    save_results()
    print(f"{job['shot']}: {rec['status']} in {rec['gpu_s']}s, peak {rec['peak_vram_gb']} GB", flush=True)
    torch.cuda.empty_cache()
