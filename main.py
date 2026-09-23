from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
from py3dbp import Packer, Bin, Item
import math

app = FastAPI(title="WooCommerce 3D Packing API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ProductItem(BaseModel):
    sku: str
    l: float
    w: float
    h: float
    weight: float
    qty: int
    color: int

class PackRequest(BaseModel):
    items: List[ProductItem]

@app.get("/")
def read_root():
    return {"status": "API Online", "mensaje": "El motor de Super-Bloques de Paletizado esta activado."}

def get_super_blocks(qty, l, w, h):
    blocks = []
    remaining = qty
    while remaining > 0:
        best_m = 1
        best_config = (1, 1, 1)
        best_score = float('inf')
        
        for m in range(1, remaining + 1):
            for a in range(1, m + 1):
                if m % a != 0: continue
                rem_a = m // a
                for b in range(1, rem_a + 1):
                    if rem_a % b != 0: continue
                    c = rem_a // b
                    
                    block_l = a * l
                    block_w = b * w
                    block_h = c * h
                    
                    max_dim = max(block_l, block_w, block_h)
                    surface_area = 2 * (block_l*block_w + block_w*block_h + block_h*block_l)
                    
                    # Criterio de eficiencia: priorizar cubos y penalizar líneas largas
                    efficiency = (surface_area + (max_dim ** 3) * 0.005) / m - (m * 5)
                    
                    if efficiency < best_score:
                        best_score = efficiency
                        best_m = m
                        best_config = (a, b, c)
                        
        blocks.append({
            "qty": best_m,
            "grid": best_config,
            "dims": (best_config[0]*l, best_config[1]*w, best_config[2]*h)
        })
        remaining -= best_m
    return blocks

@app.post("/calculate-packing")
def calculate_packing(req: PackRequest):
    items_to_pack = []
    block_id = 0
    total_vol = 0
    
    # 1. Agrupar items en Super-Bloques
    for it in req.items:
        blocks = get_super_blocks(it.qty, it.l, it.w, it.h)
        for blk in blocks:
            items_to_pack.append({
                "id": f"{it.sku}_blk{block_id}",
                "sku": it.sku,
                "color": it.color,
                "orig_dims": (it.l, it.w, it.h),
                "grid": blk["grid"],
                "block_dims": blk["dims"]
            })
            block_id += 1
            total_vol += blk["dims"][0] * blk["dims"][1] * blk["dims"][2]
            
    if not items_to_pack:
        raise HTTPException(status_code=400, detail="Sin items")

    max_dim = max(max(blk["block_dims"]) for blk in items_to_pack)
    ideal_side = max(max_dim, math.pow(total_vol * 1.2, 1/3))

    best_packer = None
    min_bounding_vol = float('inf')

    # 2. Empacar los Mega-Bloques usando py3dbp
    multipliers = [1.0, 1.25, 1.5, 2.0, 3.0, 5.0]
    
    for w_mult in multipliers:
        for d_mult in multipliers:
            test_w = ideal_side * w_mult
            test_d = ideal_side * d_mult
            
            packer = Packer()
            packer.add_bin(Bin('Virtual', test_w, test_d, 999999.0, 999999.0))

            for blk in items_to_pack:
                packer.add_item(Item(blk["id"], blk["block_dims"][0], blk["block_dims"][1], blk["block_dims"][2], 1))

            packer.pack()
            
            if len(packer.bins[0].items) == len(items_to_pack):
                m_l = m_w = m_h = 0
                for item in packer.bins[0].items:
                    x, y, z = item.position
                    l, w, h = item.get_dimension()
                    if x + l > m_l: m_l = x + l
                    if y + w > m_w: m_w = y + w
                    if z + h > m_h: m_h = z + h
                
                real_vol = m_l * m_w * m_h
                
                if real_vol < min_bounding_vol:
                    min_bounding_vol = real_vol
                    best_packer = packer

    if not best_packer:
        raise HTTPException(status_code=400, detail="No se pudo empaquetar")

    # 3. Desempacar los Mega-Bloques de vuelta a cajas individuales para el visor 3D
    placed_items = []
    max_l = max_w = max_h = 0
    b = best_packer.bins[0]
    
    for packed_item in b.items:
        x, y, z = packed_item.position
        fL, fW, fH = packed_item.get_dimension()
        
        blk = next(b for b in items_to_pack if b["id"] == packed_item.name)
        oL, oW, oH = blk["orig_dims"]
        cA, cB, cC = blk["grid"]
        
        b_dims = [ (oL*cA, oL, cA), (oW*cB, oW, cB), (oH*cC, oH, cC) ]
        used = [False, False, False]
        mapped = []
        
        for target in (fL, fW, fH):
            for i in range(3):
                if not used[i] and math.isclose(target, b_dims[i][0], rel_tol=1e-3):
                    mapped.append(b_dims[i])
                    used[i] = True
                    break
        
        if len(mapped) != 3:
            mapped = b_dims # Fallback de seguridad
            
        dx, cx = mapped[0][1], mapped[0][2]
        dy, cy = mapped[1][1], mapped[1][2]
        dz, cz = mapped[2][1], mapped[2][2]
        
        for i in range(cx):
            for j in range(cy):
                for k in range(cz):
                    child_x = float(x + i * dx)
                    child_y = float(y + j * dy)
                    child_z = float(z + k * dz)
                    
                    placed_items.append({
                        "sku": blk["sku"],
                        "x": child_x,
                        "y": child_y,
                        "z": child_z,
                        "l": float(dx),
                        "w": float(dy),
                        "h": float(dz),
                        "color": blk["color"]
                    })
                    
                    if child_x + dx > max_l: max_l = child_x + dx
                    if child_y + dy > max_w: max_w = child_y + dy
                    if child_z + dz > max_h: max_h = child_z + dz

    return {
        "bounding_box": {"l": float(max_l), "w": float(max_w), "h": float(max_h)},
        "placed_items": placed_items
    }
