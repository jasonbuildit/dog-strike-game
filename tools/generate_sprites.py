"""
DogStrike Hero Sprite Generator
================================
Generates 11 animation frames per hero using Stable Diffusion XL + IP-Adapter.
Requires: pip install diffusers transformers accelerate torch Pillow rembg

Usage:
  cd /Users/jasso/workspace/dog-strike-game
  source ~/comfyui-env/bin/activate
  python tools/generate_sprites.py                  # all heroes, all frames
  python tools/generate_sprites.py saint            # one hero
  python tools/generate_sprites.py saint idle_a     # one frame (debug)
  python tools/generate_sprites.py --download-only  # pre-download models only
"""

import os, sys, warnings, argparse
warnings.filterwarnings("ignore")

SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
GAME_DIR     = os.path.dirname(SCRIPT_DIR)
GEN_DIR      = os.path.join(SCRIPT_DIR, "generated")
ASSETS_DIR   = os.path.join(GAME_DIR, "assets", "dogs")

# ---------------------------------------------------------------------------
# Model identifiers
# ---------------------------------------------------------------------------
SDXL_MODEL_ID  = "RunDiffusion/Juggernaut-XL-v9"
IPA_REPO_ID    = "h94/IP-Adapter"
IPA_SUBFOLDER  = "sdxl_models"
IPA_WEIGHT     = "ip-adapter_sdxl.bin"     # uses built-in SDXL CLIP-L encoder

# ---------------------------------------------------------------------------
# Frame layout — 11 frames, left to right in the sprite sheet
# ---------------------------------------------------------------------------
FRAME_SEQ = [
    "idle_a", "idle_b",
    "walk_a", "walk_b", "walk_c", "walk_d",
    "jump",
    "strike",
    "special_a", "special_b", "special_c",
]

FRAME_POSE = {
    "idle_a":    "standing upright relaxed, arms loose at sides, weight centered, facing right",
    "idle_b":    "slight torso rise, chin tilted up slightly, subtle breath pose, facing right",
    "walk_a":    "walking stride, right leg forward left leg back, body leaning right, facing right",
    "walk_b":    "mid-stride, both legs centered, neutral upright torso, facing right",
    "walk_c":    "walking stride, left leg forward right leg back, body leaning left, facing right",
    "walk_d":    "mid-stride, both legs centered, neutral upright torso, facing right",
    "jump":      "airborne jump, both legs tucked up, arms raised overhead, tail up, exuberant",
    "strike":    "punching forward with dominant paw, body leaned forward 15 degrees, fierce",
    "special_a": "power windup pose, pulling back with both arms, charging energy, anticipation",
    "special_b": "peak power pose, mouth open wide, front paws raised, energy burst around head",
    "special_c": "power release, arms thrust forward, energy exploding outward, triumphant",
}

# ---------------------------------------------------------------------------
# Per-hero character prompts
# ---------------------------------------------------------------------------
HERO_BASE = (
    "Art Deco 1930s union poster illustration style, {character}, "
    "full body character sprite, {pose}, "
    "pure solid white background, single character centered, "
    "bold clean illustration linework, gold and teal accents, "
    "warm expressive eyes, adorable and determined expression"
)
HERO_NEG = (
    "multiple characters, busy background, text, watermark, blurry, "
    "realistic photograph, 3D render, deformed, extra limbs"
)

HEROES = {
    "saint": {
        "character": (
            "English Bulldog worker dog, stocky build, brown and white fur, "
            "wrinkled expressive jowls, small hard hat with gear emblem on head, "
            "bright orange bandana neckerchief tied around neck, "
            "thick muscular paws, determined heroic expression"
        ),
        "ref_image": os.path.join(ASSETS_DIR, "hero_saint_body.png"),
    },
    "shepherd": {
        "character": (
            "German Shepherd dog, tall athletic build, black and tan fur, "
            "alert pointed ears, teal military captain hat with brass eagle badge, "
            "noble intelligent expression, proud commanding stance"
        ),
        "ref_image": os.path.join(ASSETS_DIR, "hero_shepherd_body.png"),
    },
    "dachshund": {
        "character": (
            "Airedale Terrier dog, compact wiry build, reddish-brown curly fur, "
            "copper miner's helmet with glowing front lamp, "
            "teal green scarf wrapped around neck, "
            "clever mischievous expression, glowing teal circuit lines on paws"
        ),
        "ref_image": os.path.join(ASSETS_DIR, "hero_dachshund_body.png"),
    },
}

# ---------------------------------------------------------------------------
# Generation settings
# ---------------------------------------------------------------------------
GEN_WIDTH      = 512
GEN_HEIGHT     = 640
NUM_STEPS      = 28
GUIDANCE_SCALE = 7.5
IPA_SCALE      = 0.55   # 0 = ignore ref, 1 = copy ref; 0.55 balances pose freedom + char identity
SEED_BASE      = 42     # deterministic; change to resample


def load_pipeline():
    import torch
    from diffusers import StableDiffusionXLPipeline

    print(f"Loading SDXL model: {SDXL_MODEL_ID}")
    print("  (First run downloads ~6 GB to ~/.cache/huggingface)")

    # Load fp16 variant (that's what's cached), then cast to float32 for CPU
    pipe = StableDiffusionXLPipeline.from_pretrained(
        SDXL_MODEL_ID,
        torch_dtype=torch.float16,
        use_safetensors=True,
        variant="fp16",
    )
    pipe = pipe.to(torch.float32)

    # Load model to CPU — 32 GB system RAM handles SDXL comfortably.
    # MPS (4 GB VRAM) can't fit the full model + IP-Adapter simultaneously.
    # CPU inference: ~3-5 min per frame. 33 frames = ~2-3 hours total.
    print("  Device: cpu (32 GB RAM, ~3-5 min/frame)")

    print(f"Loading IP-Adapter: {IPA_REPO_ID}/{IPA_SUBFOLDER}/{IPA_WEIGHT}")
    print("  (Downloads ~2 GB on first run)")
    pipe.load_ip_adapter(IPA_REPO_ID, subfolder=IPA_SUBFOLDER, weight_name=IPA_WEIGHT)
    pipe.set_ip_adapter_scale(IPA_SCALE)

    device = "cpu"

    return pipe, device


def remove_background(img):
    """
    Strip white background from an illustrated character image using PIL.
    Works best with the 'flat solid white background' prompt we inject.
    Uses color-distance thresholding + edge softening.
    """
    from PIL import Image, ImageFilter
    import numpy as np

    img_rgba = img.convert("RGBA")
    data = np.array(img_rgba, dtype=np.float32)

    # Background color sampled from corners (should be near-white)
    corners = [
        data[0, 0, :3], data[0, -1, :3],
        data[-1, 0, :3], data[-1, -1, :3],
    ]
    bg_color = np.mean(corners, axis=0)  # e.g. [255, 255, 255]

    # Euclidean distance from background color in RGB space
    diff = np.linalg.norm(data[:, :, :3] - bg_color, axis=2)

    # Threshold: pixels within 40 units of bg → transparent
    # pixels beyond 80 units → fully opaque
    lo, hi = 30.0, 80.0
    alpha = np.clip((diff - lo) / (hi - lo), 0, 1) * 255
    alpha = alpha.astype(np.uint8)

    # Blur alpha slightly for soft edges
    alpha_img = Image.fromarray(alpha, mode="L").filter(ImageFilter.GaussianBlur(1.5))
    img_rgba.putalpha(alpha_img)
    return img_rgba


def generate_frame(pipe, device, hero_id: str, frame_name: str, ref_image) -> None:
    import torch
    from PIL import Image

    out_path = os.path.join(GEN_DIR, f"{hero_id}_{frame_name}.png")
    if os.path.exists(out_path):
        print(f"    skip {hero_id}_{frame_name}.png  (exists)")
        return

    hero     = HEROES[hero_id]
    pose     = FRAME_POSE[frame_name]
    prompt   = HERO_BASE.format(character=hero["character"], pose=pose)

    generator = torch.Generator().manual_seed(SEED_BASE + FRAME_SEQ.index(frame_name))

    print(f"    generating {hero_id}_{frame_name}.png …")
    result = pipe(
        prompt=prompt,
        negative_prompt=HERO_NEG,
        ip_adapter_image=ref_image,
        num_inference_steps=NUM_STEPS,
        guidance_scale=GUIDANCE_SCALE,
        width=GEN_WIDTH,
        height=GEN_HEIGHT,
        generator=generator,
    ).images[0]

    # Remove background
    result_rgba = remove_background(result)

    # Crop to content bounding box (removes empty border)
    bbox = result_rgba.getbbox()
    if bbox:
        result_rgba = result_rgba.crop(bbox)

    result_rgba.save(out_path, "PNG")
    print(f"    saved  → {out_path}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("hero", nargs="?", choices=list(HEROES.keys()),
                        help="Generate only this hero (default: all)")
    parser.add_argument("frame", nargs="?", choices=FRAME_SEQ,
                        help="Generate only this frame (requires hero)")
    parser.add_argument("--download-only", action="store_true",
                        help="Pre-download models without generating any images")
    args = parser.parse_args()

    os.makedirs(GEN_DIR, exist_ok=True)

    pipe, device = load_pipeline()

    if args.download_only:
        print("Models downloaded successfully. Run without --download-only to generate sprites.")
        return

    from PIL import Image
    heroes_to_run = [args.hero] if args.hero else list(HEROES.keys())
    frames_to_run = [args.frame] if args.frame else FRAME_SEQ

    for hero_id in heroes_to_run:
        hero = HEROES[hero_id]
        print(f"\n[{hero_id}]")

        # Load reference image
        if os.path.exists(hero["ref_image"]):
            ref_image = Image.open(hero["ref_image"]).convert("RGB")
            print(f"  reference: {hero['ref_image']}")
        else:
            print(f"  WARNING: reference image not found: {hero['ref_image']}")
            print("  Generating without IP-Adapter reference")
            ref_image = None
            pipe.set_ip_adapter_scale(0.0)

        for frame_name in frames_to_run:
            generate_frame(pipe, device, hero_id, frame_name, ref_image)

    print("\nAll frames generated.")
    print("Run: python tools/assemble_sheet.py")
    print("Then reload http://localhost:8080/dogstrike.html")


if __name__ == "__main__":
    main()
