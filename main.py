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
    best_packer = None
    min_bounding_vol = float('inf')

    min_side = int(max_item_dim)
    # Rango de prueba para el piso. Aseguramos al menos un buen margen.
    max_side = int(max(min_side * 3, math.pow(total_vol * 4, 1/3))) 
    step = max(5, (max_side - min_side) // 12)

    # 1) Prueba estricta: Simulamos cajas con PAREDES FISICAS para forzar la densidad
    # y evitar formas de "L" o piezas desparramadas.
    for test_w in range(min_side, max_side + step, step):
        for test_d in range(min_side, max_side + step, step):
            packer = Packer()
            packer.add_bin(Bin('Virtual', test_w, test_d, 999999.0, 999999.0))

            for it in req.items:
                for i in range(it.qty):
                    packer.add_item(Item(f"{it.sku}_{i}", it.l, it.w, it.h, it.weight))

            packer.pack()
            
            if len(packer.bins[0].items) == total_items:
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

    # 2) Fallback: Si ningún contenedor estricto funcionó (combinación muy rara)
    if not best_packer:
        packer = Packer()
        packer.add_bin(Bin('Fallback', 999999.0, 999999.0, 999999.0, 999999.0))
        for it in req.items:
            for i in range(it.qty):
                packer.add_item(Item(f"{it.sku}_{i}", it.l, it.w, it.h, it.weight))
        packer.pack()
        if len(packer.bins[0].items) == total_items:
            best_packer = packer

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
