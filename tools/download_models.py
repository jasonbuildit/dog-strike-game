"""
Pre-download all models needed for sprite generation.
Run this once (overnight if needed) before generate_sprites.py.

Usage:
  source ~/comfyui-env/bin/activate
  python tools/download_models.py

Downloads to ~/.cache/huggingface/hub/ (~8-9 GB total):
  - RunDiffusion/Juggernaut-XL-v9   fp16 safetensors  (~6 GB)
  - h94/IP-Adapter                  sdxl ip-adapter    (~2 GB)
  - briaai/RMBG-1.4                 rembg model        (~170 MB)
"""

import os, warnings
warnings.filterwarnings("ignore")

def download_sdxl():
    from diffusers import StableDiffusionXLPipeline
    import torch
    print("Downloading Juggernaut XL v9 (~6 GB)...")
    pipe = StableDiffusionXLPipeline.from_pretrained(
        "RunDiffusion/Juggernaut-XL-v9",
        torch_dtype=torch.float16,
        use_safetensors=True,
        variant="fp16",
    )
    print("  SDXL checkpoint: OK")
    return pipe

def download_ipadapter(pipe):
    print("Downloading IP-Adapter SDXL (~2 GB)...")
    pipe.load_ip_adapter(
        "h94/IP-Adapter",
        subfolder="sdxl_models",
        weight_name="ip-adapter_sdxl.bin",
    )
    print("  IP-Adapter: OK")

def download_rembg():
    print("Downloading rembg background removal model (~170 MB)...")
    try:
        from rembg import new_session
        session = new_session("u2net")
        print("  rembg u2net: OK")
    except Exception as e:
        print(f"  rembg: {e} (will skip background removal during generation)")

if __name__ == "__main__":
    print("=" * 60)
    print("DogStrike model pre-downloader")
    print("=" * 60)
    pipe = download_sdxl()
    download_ipadapter(pipe)
    download_rembg()
    print("\nAll models cached. Run generate_sprites.py to generate frames.")
