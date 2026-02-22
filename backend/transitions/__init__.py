"""
Plugin system de transições — auto-discovery.

Scaneia todos os *.py nesta pasta (exceto __init__.py e arquivos com prefixo _),
importa cada módulo e registra as transições que seguem o contrato:
  NAME: str, LABEL: str, DESCRIPTION: str, apply(seg1, seg2, sr, **kwargs) → mixed
"""

import importlib
import pkgutil
from pathlib import Path

_REQUIRED_ATTRS = ("NAME", "LABEL", "DESCRIPTION", "apply")

# Registros populados pelo auto-discovery
TRANSITIONS = {}       # {name: apply_func}
TRANSITION_LIST = []   # [name, ...]
TRANSITION_INFO = []   # [{name, label, description}, ...]


def _discover():
    """Scaneia a pasta, importa módulos e registra transições válidas."""
    package_dir = Path(__file__).parent

    for finder, module_name, is_pkg in pkgutil.iter_modules([str(package_dir)]):
        # Ignorar arquivos com prefixo _ (como _utils.py)
        if module_name.startswith("_"):
            continue

        try:
            mod = importlib.import_module(f"transitions.{module_name}")
        except Exception as e:
            print(f"[transitions] Erro ao importar {module_name}: {e}")
            continue

        # Validar contrato
        missing = [attr for attr in _REQUIRED_ATTRS if not hasattr(mod, attr)]
        if missing:
            print(f"[transitions] {module_name} ignorado — faltam: {', '.join(missing)}")
            continue

        name = mod.NAME
        TRANSITIONS[name] = mod.apply
        TRANSITION_INFO.append({
            "name": name,
            "label": mod.LABEL,
            "description": mod.DESCRIPTION,
        })

    # Ordenar pra ter ordem consistente (eq_mix primeiro como default)
    order = ["eq_mix", "crossfade", "filter_sweep", "echo_out", "cut"]
    TRANSITION_INFO.sort(key=lambda x: order.index(x["name"]) if x["name"] in order else 999)
    TRANSITION_LIST.extend([t["name"] for t in TRANSITION_INFO])


def get_transition(name):
    """Retorna a função apply de uma transição pelo nome, com fallback pra eq_mix."""
    return TRANSITIONS.get(name, TRANSITIONS.get("eq_mix"))


# Auto-discovery ao importar o pacote
_discover()
