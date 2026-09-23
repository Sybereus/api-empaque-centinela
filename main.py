from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
import math

app = FastAPI(title="WooCommerce 3D Packing API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

class ProductItem(BaseModel):
    sku: str; l: float; w: float; h: float; weight: float; qty: int; color: int

class PackRequest(BaseModel):
    items: List[ProductItem]

@app.get("/")
def read_root(): return {"status": "API Online", "mensaje": "Algoritmo Drop Heuristic (Apilamiento Humano) activado."}

@app.post("/calculate-packing")
def calculate_packing(req: PackRequest):
    if not req.items: raise HTTPException(status_code=400, detail="Sin items")

    boxes = []
    for it in req.items:
        # Acostar las cajas (L >= W) para asegurar que la base sea la más ancha y estable posible
        dims = sorted([float(it.l), float(it.w), float(it.h)], reverse=True)
        for _ in range(it.qty):
            boxes.append({
                "sku": it.sku, "color": it.color,
                "l": dims[0], "w": dims[1], "h": dims[2],
                "area": dims[0] * dims[1],
                "vol": dims[0] * dims[1] * dims[2]
            })

    # 1. ORDENAR: Cajas con mayor Área primero. La caja verde (grande) irá primero al piso.
    boxes.sort(key=lambda b: (b["area"], b["vol"]), reverse=True)

    # 2. DEFINIR EL PALET: Lo restringimos AL TAMAÑO DE LA CAJA MÁS GRANDE. 
    # Esto OBLIGA a que todas las cajas pequeñas se apilen ENCIMA de la grande, no a los lados.
    PALLET_L = max(b["l"] for b in boxes)
    PALLET_W = max(b["w"] for b in boxes)
    
    # Si hay muchísimas cajas y la torre pasaría de 1.5 metros, agrandamos el piso.
    total_vol = sum(b["vol"] for b in boxes)
    if total_vol > (PALLET_L * PALLET_W * 150): 
        PALLET_L = math.sqrt(total_vol / 100)
        PALLET_W = PALLET_L

    placed_items = []

    # 3. DROP HEURISTIC (Dejar caer cajas desde arriba)
    for b in boxes:
        best_z = float('inf')
        best_x, best_y = 0.0, 0.0
        best_l, best_w = b["l"], b["w"]
        
        # Escanear coordenadas donde podríamos dejar caer la caja
        x_cands, y_cands = [0.0], [0.0]
        for p in placed_items:
            x_cands.extend([p["x"], p["x"] + p["l"]])
            y_cands.extend([p["y"], p["y"] + p["w"]])
            
        x_cands = sorted(list(set(x_cands)))
        y_cands = sorted(list(set(y_cands)))
        
        # Probar orientación horizontal y rotada
        orientations = [(b["l"], b["w"])]
        if b["l"] != b["w"]: orientations.append((b["w"], b["l"]))
            
        for rot_l, rot_w in orientations:
            for x in x_cands:
                if x + rot_l > PALLET_L + 0.1: continue
                for y in y_cands:
                    if y + rot_w > PALLET_W + 0.1: continue
                    
                    # Simular dejar caer la caja aquí y ver en qué altura (Z) choca
                    drop_z = 0.0
                    for p in placed_items:
                        # Si se cruzan en el piso 2D (con un margen mínimo por decimales)...
                        if not (x >= p["x"] + p["l"] - 0.1 or x + rot_l <= p["x"] + 0.1 or
                                y >= p["y"] + p["w"] - 0.1 or y + rot_w <= p["y"] + 0.1):
                            if p["z"] + p["h"] > drop_z:
                                drop_z = p["z"] + p["h"]
                                
                    # Buscar el hueco que nos permita dejar la caja lo más abajo posible
                    if drop_z < best_z:
                        best_z = drop_z
                        best_x, best_y = x, y
                        best_l, best_w = rot_l, rot_w

        placed_items.append({
            "sku": b["sku"], "color": b["color"],
            "x": float(best_x), "y": float(best_y), "z": float(best_z),
            "l": float(best_l), "w": float(best_w), "h": float(b["h"])
        })

    max_l = max([p["x"] + p["l"] for p in placed_items] + [0.0])
    max_w = max([p["y"] + p["w"] for p in placed_items] + [0.0])
    max_h = max([p["z"] + p["h"] for p in placed_items] + [0.0])

    return {
        "bounding_box": {"l": float(max_l), "w": float(max_w), "h": float(max_h)},
        "placed_items": placed_items
    }
