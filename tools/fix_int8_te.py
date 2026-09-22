r"""Contournement pour sd.cpp : le fichier qwen3vl_8b_int8_convrot.safetensors (Comfy-Org) contient
une table d'embeddings (model.embed_tokens) et un lm_head quantifiés en int8 ; sd.cpp (commit 74988b2)
en déduit un hidden_size erroné (151936) et plante. Ce script :
  - déquantifie model.embed_tokens en bf16 (dé-rotation Hadamard si convrot=true),
  - supprime lm_head (inutile pour un encodeur de texte),
  - copie tel quel tout le reste (couches int8 convrot conservées => mémoire préservée).
Usage : python tools/fix_int8_te.py SRC.safetensors DST.safetensors
"""
import json, struct, sys, os
import numpy as np

def h4():
    return np.array([[1, 1, 1, -1], [1, 1, -1, 1], [1, -1, 1, 1], [-1, 1, 1, 1]], dtype=np.float32) / 2.0

def hadamard(group):
    H = np.array([[1.0]], dtype=np.float32)
    while H.shape[0] < group:
        H = np.kron(H, h4())
    assert H.shape[0] == group, group
    return H

def to_bf16_bytes(a):
    a = np.ascontiguousarray(a, dtype=np.float32)
    u = a.view(np.uint32)
    # arrondi au plus proche (round-to-nearest-even) vers bf16
    rounded = ((u + 0x7FFF + ((u >> 16) & 1)) >> 16).astype(np.uint16)
    return rounded.tobytes()

def main(src, dst):
    f = open(src, "rb")
    n = struct.unpack("<Q", f.read(8))[0]
    header = json.loads(f.read(n))
    base = 8 + n
    meta = header.pop("__metadata__", {"format": "pt"})
    names = sorted(header, key=lambda k: header[k]["data_offsets"][0])
    vis = [k for k in names if "visual" in k or "vision" in k]
    print(f"{len(names)} tenseurs, dont {len(vis)} de la tour vision ; ex: {vis[:3]}")

    def read(k):
        s, e = header[k]["data_offsets"]; f.seek(base + s); return f.read(e - s)

    emb_q = json.loads(bytes(np.frombuffer(read("model.embed_tokens.comfy_quant"), dtype=np.uint8)).decode("utf-8", "ignore").strip("\x00"))
    print("comfy_quant embed_tokens :", emb_q)
    print("comfy_quant layer0 q_proj :", json.loads(bytes(np.frombuffer(read("model.layers.0.self_attn.q_proj.comfy_quant"), dtype=np.uint8)).decode("utf-8", "ignore").strip("\x00")))

    # déquantification de l'embedding
    shp = header["model.embed_tokens.weight"]["shape"]
    W = np.frombuffer(read("model.embed_tokens.weight"), dtype=np.int8).reshape(shp).astype(np.float32)
    S = np.frombuffer(read("model.embed_tokens.weight_scale"), dtype=np.float32).reshape(-1, 1)
    W *= S
    if emb_q.get("convrot"):
        g = int(emb_q.get("convrot_groupsize", 256)); H = hadamard(g)
        W = (W.reshape(shp[0], shp[1] // g, g) @ H).reshape(shp)   # R symétrique : W = W_rot R
        print(f"dé-rotation Hadamard appliquée (groupe {g})")
    emb_bytes = to_bf16_bytes(W); del W

    skip = {"model.embed_tokens.weight", "model.embed_tokens.weight_scale", "model.embed_tokens.comfy_quant",
            "lm_head.weight", "lm_head.weight_scale", "lm_head.comfy_quant"}
    new_header = {"__metadata__": meta}; off = 0; plan = []
    for k in names:
        if k in skip: continue
        s, e = header[k]["data_offsets"]; size = e - s
        new_header[k] = {"dtype": header[k]["dtype"], "shape": header[k]["shape"], "data_offsets": [off, off + size]}; plan.append((k, s, size)); off += size
    new_header["model.embed_tokens.weight"] = {"dtype": "BF16", "shape": shp, "data_offsets": [off, off + len(emb_bytes)]}; off += len(emb_bytes)
    hb = json.dumps(new_header, separators=(",", ":")).encode("utf-8"); hb += b" " * ((8 - len(hb) % 8) % 8)
    with open(dst, "wb") as o:
        o.write(struct.pack("<Q", len(hb))); o.write(hb)
        for k, s, size in plan:
            f.seek(base + s); left = size
            while left:
                chunk = f.read(min(left, 64 << 20)); o.write(chunk); left -= len(chunk)
        o.write(emb_bytes)
    print(f"écrit : {dst} ({os.path.getsize(dst):,} octets)")

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
