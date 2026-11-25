"""Cloudflare Workers AI image generation (FLUX.2 klein 4B, FLUX.1 schnell fallback)."""

from __future__ import annotations

import base64
import io
import math
from pathlib import Path
from typing import Any

from PIL import Image

from pipeline.core.calls import ProviderError
from pipeline.core.config import provider_cfg, secret
from pipeline.providers.base import post


def _tiles(w: int, h: int) -> int:
    return math.ceil(w / 512) * math.ceil(h / 512)


def _downscale_ref(path: Path, max_side: int) -> bytes:
    """klein reference inputs must be smaller than 512x512."""
    img = Image.open(path).convert("RGB")
    img.thumbnail((max_side, max_side), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class CloudflareImage:
    name = "cloudflare"

    def __init__(self, model: str | None = None) -> None:
        self.cfg = provider_cfg("image")
        self.model = model or self.cfg["model"]

    def _url(self) -> str:
        account = secret("CF_ACCOUNT_ID")
        return f"https://api.cloudflare.com/client/v4/accounts/{account}/ai/run/{self.model}"

    def generate(
        self, prompt: str, out: Path, *, seed: int, width: int, height: int, refs: list[Path]
    ) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {secret('CF_API_TOKEN')}"}
        if "klein" in self.model:
            fields: dict[str, Any] = {
                "prompt": (None, prompt),
                "width": (None, str(width)),
                "height": (None, str(height)),
                "seed": (None, str(seed)),
            }
            for i, ref in enumerate(refs[:4]):
                data = _downscale_ref(ref, self.cfg["max_ref_side"])
                fields[f"input_image_{i}"] = (f"ref{i}.png", data, "image/png")
            resp = post(self._url(), self.name, headers=headers, files=fields)
        else:  # flux-1-schnell: JSON body, no references
            resp = post(
                self._url(),
                self.name,
                headers=headers,
                json={"prompt": prompt[:2048], "seed": seed, "steps": 4},
            )

        if resp.headers.get("content-type", "").startswith("image/"):
            raw = resp.content
        else:
            body = resp.json()
            result = body.get("result", body)
            b64 = result.get("image") if isinstance(result, dict) else None
            if not b64:
                raise ProviderError(f"cloudflare: no image in response: {str(body)[:200]}")
            raw = base64.b64decode(b64)

        img = Image.open(io.BytesIO(raw)).convert("RGB")
        got = img.size
        if got != (width, height):
            img = img.resize((width, height), Image.LANCZOS)
        img.save(out, format="PNG")

        neurons = _tiles(width, height) * self.cfg["neurons_per_output_tile"]
        neurons += len(refs[:4]) * self.cfg["neurons_per_input_tile"]
        if "klein" not in self.model:
            neurons = 4.8 * _tiles(*got) + 9.6 * 4
        return {
            "est_neurons": round(neurons, 1),
            "est_cost_usd": round(neurons / 1000 * self.cfg["usd_per_1k_neurons"], 5),
            "returned_size": list(got),
            "n_refs": len(refs[:4]),
        }
