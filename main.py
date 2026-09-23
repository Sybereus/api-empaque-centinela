from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
from py3dbp import Packer, Bin, Item

app = FastAPI(title="WooCommerce 3D Packing API")

# Permitir CORS para que WordPress pueda consultar esta API
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

@app.post("/calculate-packing")
def calculate_packing(req: PackRequest):
    packer = Packer()

    # Como queremos el volumen mínimo y no tenemos una "caja fija", 
    # creamos una caja "virtual" lo suficientemente grande
    # En una implementación más avanzada, se iteraría para reducir esta caja al mínimo absoluto.
    max_dim = 0
    total_vol = 0
    for it in req.items:
        max_dim += max(it.l, it.w, it.h) * it.qty
        total_vol += (it.l * it.w * it.h) * it.qty

    # Bin gigante virtual
    packer.add_bin(Bin('Virtual-Bin', max_dim, max_dim, max_dim, 999999.0))

    for it in req.items:
        for i in range(it.qty):
            packer.add_item(Item(f"{it.sku}_{i}", it.l, it.w, it.h, it.weight))

    packer.pack()

    b = packer.bins[0]
    
    if not b.items:
        raise HTTPException(status_code=400, detail="No se pudo empaquetar")

    placed_items = []
    max_l, max_w, max_h = 0, 0, 0

    # Extraer coordenadas del motor py3dbp
    for item in b.items:
        # py3dbp devuelve position (x,y,z) y dimensiones rotadas
        x, y, z = item.position
        
        # Las dimensiones actuales según la rotación aplicada por py3dbp
        l, w, h = item.get_dimension()
        
        # Mapear color
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
        "bounding_box": {
            "l": float(max_l),
            "w": float(max_w),
            "h": float(max_h)
        },
        "placed_items": placed_items
    }

# Para correr en local: uvicorn main:app --reload
