from dataclasses import dataclass
from typing import Optional, Dict, Tuple, List

@dataclass
class Models:
    reg: Optional[object] = None
    clf: Optional[object] = None

def load_models(reg_path: str, clf_path: str) -> Models:
    # placeholder: implement later if you add LightGBM
    return Models(None, None)

def predict(models: Models, feats: Dict[str, float]) -> Tuple[Optional[float], Optional[List[float]]]:
    return None, None
