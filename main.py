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
    return {"status": "API Online", "mensaje": "El motor de empaque 3D en Python esta funcionando correctamente."}

@app.post("/calculate-packing")
def calculate_packing(req: PackRequest):
    total_vol = 0
    max_item_dim = 0
    total_items = 0
    for it in req.items:
        total_vol += (it.l * it.w * it.h) * it.qty
        max_item_dim = max(max_item_dim, it.l, it.w, it.h)
        total_items += it.qty

    # Para forzar un paquete cúbico compacto, restringimos el piso virtual.
    # El lado de un cubo ideal es la raíz cúbica del volumen total (+20% de holgura).
    ideal_side = max(max_item_dim, math.pow(total_vol * 1.2, 1/3))

    best_packer = None

    # Intentamos empacar en bases gradualmente más grandes si no cabe
    for multiplier in [1.0, 1.2, 1.5, 2.0, 3.0, 10.0]:
        floor_size = ideal_side * multiplier
        
        packer = Packer()
        # Creamos una caja con "paredes" estrechas pero altura infinita para forzar el apilamiento
        packer.add_bin(Bin('Virtual-Bin', floor_size, floor_size, 999999.0, 999999.0))

        for it in req.items:
            for i in range(it.qty):
                packer.add_item(Item(f"{it.sku}_{i}", it.l, it.w, it.h, it.weight))

        packer.pack()
        
        # Si empacó todos los items, este tamaño de base es suficiente
        if len(packer.bins[0].items) == total_items:
            best_packer = packer
            break

    if not best_packer:
        raise HTTPException(status_code=400, detail="No se pudo empaquetar")

    b = best_packer.bins[0]
    placed_items = []
    max_l, max_w, max_h = 0, 0, 0

    for item in b.items:
        x, y, z = item.position
        l, w, h = item.get_dimension()
        
        color = 0x000000
        for req_item in req.items:
            if item.name.startswith(req_item.sku):
                color = req_item.color
                break

        placed_items.append({
            "sku": item.name.split('_')[0],
            "x": float(x),
            "y": float(y),
            "z": float(z),
            "l": float(l),
            "w": float(w),
            "h": float(h),
            "color": color
        })

        if x + l > max_l: max_l = x + l
        if y + w > max_w: max_w = y + w
        if z + h > max_h: max_h = z + h

    return {
        "bounding_box": {"l": float(max_l), "w": float(max_w), "h": float(max_h)},
        "placed_items": placed_items
    }
