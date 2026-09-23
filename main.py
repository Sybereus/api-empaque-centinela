from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
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
    return {"status": "API Online", "mensaje": "Motor de Paletizado Físico (Gravedad) activado."}

@app.post("/calculate-packing")
def calculate_packing(req: PackRequest):
    if not req.items:
        raise HTTPException(status_code=400, detail="Sin items")

    boxes = []
    total_vol = 0.0
    
    # 1. Estandarizar rotación: Base más ancha posible para máxima estabilidad
    for it in req.items:
        for _ in range(it.qty):
            # Ordenamos las dimensiones de mayor a menor: L >= W >= H
            dims = sorted([float(it.l), float(it.w), float(it.h)], reverse=True)
            boxes.append({
                "sku": it.sku, "color": it.color,
                "l": dims[0], "w": dims[1], "h": dims[2]
            })
            total_vol += (dims[0] * dims[1] * dims[2])

    # 2. Ordenar las cajas: Más altas primero, luego más grandes (para hacer pisos firmes)
    boxes.sort(key=lambda x: (x["h"], x["l"] * x["w"]), reverse=True)

    # 3. Calcular un tamaño de piso (Footprint) ideal para el palet
    # Usamos la raíz cúbica del volumen para buscar forma de cubo, pero garantizamos que quepa la caja más grande.
    ideal_side = math.pow(total_vol * 1.2, 1/3)
    max_l = max([b["l"] for b in boxes] + [0])
    max_w = max([b["w"] for b in boxes] + [0])
    
    PALLET_L = max(ideal_side, max_l)
    PALLET_W = max(ideal_side, max_w)

    placed_items = []
    current_z = 0.0
    current_y = 0.0
    current_x = 0.0
    
    row_depth = 0.0
    layer_height = 0.0

    # 4. Algoritmo de "Estantería" (Shelf Algorithm) - Apilamiento con Gravedad Real
    for b in boxes:
        # ¿Cabe en la fila actual (eje X)?
        if current_x + b["l"] > PALLET_L:
            current_x = 0.0
            current_y += row_depth
            row_depth = 0.0
            
        # ¿Cabe en la capa/piso actual (eje Y)?
        if current_y + b["w"] > PALLET_W:
            current_z += layer_height
            current_x = 0.0
            current_y = 0.0
            row_depth = 0.0
            layer_height = 0.0
            
        # Posicionar caja
        placed_items.append({
            "sku": b["sku"],
            "color": b["color"],
            "x": current_x,
            "y": current_y,
            "z": current_z,
            "l": b["l"],
            "w": b["w"],
            "h": b["h"]
        })
        
        # Avanzar el puntero en X
        current_x += b["l"]
        
        # Actualizar dimensiones máximas de la fila y de la capa
        if b["w"] > row_depth:
            row_depth = b["w"]
        if b["h"] > layer_height:
            layer_height = b["h"]

    # Calcular la Bounding Box final
    final_l = max([p["x"] + p["l"] for p in placed_items] + [0])
    final_w = max([p["y"] + p["w"] for p in placed_items] + [0])
    final_h = max([p["z"] + p["h"] for p in placed_items] + [0])

    return {
        "bounding_box": {"l": final_l, "w": final_w, "h": final_h},
        "placed_items": placed_items
    }
