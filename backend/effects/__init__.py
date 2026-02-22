"""
Plugin system de efeitos de transicao — auto-discovery.

Scaneia todos os *.py nesta pasta (exceto __init__.py e arquivos com prefixo _),
importa cada modulo e registra os efeitos que seguem o contrato:
  NAME: str, LABEL: str, DESCRIPTION: str, generate(duration_samples, sr, **kwargs) -> (2, samples)
"""

import importlib
import pkgutil
from pathlib import Path

_REQUIRED_ATTRS = ("NAME", "LABEL", "DESCRIPTION", "generate")

# Registros populados pelo auto-discovery
EFFECTS = {}        # {name: module}
EFFECT_LIST = []    # [name, ...]
EFFECT_INFO = []    # [{name, label, description}, ...]


def _discover():
    """Scaneia a pasta, importa modulos e registra efeitos validos."""
    package_dir = Path(__file__).parent

    for finder, module_name, is_pkg in pkgutil.iter_modules([str(package_dir)]):
        # Ignorar arquivos com prefixo _ (como _utils.py)
        if module_name.startswith("_"):
            continue

        try:
            mod = importlib.import_module(f"effects.{module_name}")
        except Exception as e:
            print(f"[effects] Erro ao importar {module_name}: {e}")
            continue

        # Validar contrato
        missing = [attr for attr in _REQUIRED_ATTRS if not hasattr(mod, attr)]
        if missing:
            print(f"[effects] {module_name} ignorado — faltam: {', '.join(missing)}")
            continue

        name = mod.NAME
        EFFECTS[name] = mod
        EFFECT_INFO.append({
            "name": name,
            "label": mod.LABEL,
            "description": mod.DESCRIPTION,
        })

    # Ordenar pra ter ordem consistente
    order = [
        "noise_riser", "reverse_crash", "siren_rise", "shimmer_rise",
        "sub_boom", "impact_clap", "downsweep", "tension_pad",
        "white_wash", "vinyl_crackle", "telephone", "laser_zap",
    ]
    EFFECT_INFO.sort(key=lambda x: order.index(x["name"]) if x["name"] in order else 999)
    EFFECT_LIST.extend([e["name"] for e in EFFECT_INFO])


def get_effect(name):
    """Retorna o modulo de um efeito pelo nome, ou None se nao existir."""
    return EFFECTS.get(name)


# Auto-discovery ao importar o pacote
_discover()
