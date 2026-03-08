#!/usr/bin/env python3
"""
Export a Pydantic model *tree* (main + all nested child models) to Markdown.

Usage:
  1) Edit the import below to point to your main model:
       from myapp.models import RootModel as MAIN_MODEL
  2) Run:
       python export_main_pydantic_tree_md.py --out docs/models.md --title "My Models"
"""

from __future__ import annotations

from common.models.agoge import CatalogModel as MAIN_MODEL

# -----------------------------------------------------------------------------

import argparse
import inspect
import io
import json
import sys
import types
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple, Union, get_args, get_origin

# Pydantic compatibility
try:
    from pydantic import BaseModel, Field
except Exception:
    print("Pydantic is required. Install with: pip install pydantic", file=sys.stderr)
    raise

# ------------------------------------------------------------------------------------
# Pydantic v1/v2 helpers
# ------------------------------------------------------------------------------------

def is_pydantic_model(obj: Any) -> bool:
    try:
        return inspect.isclass(obj) and issubclass(obj, BaseModel) and obj is not BaseModel
    except Exception:
        return False

def has_v2_fields(model: type) -> bool:
    return hasattr(model, "model_fields")

def iter_model_fields(model: type):
    """
    Yield (field_name, field_obj, annotation) uniformly for v1 and v2.
    """
    if hasattr(model, "model_fields"):  # v2
        for name, f in model.model_fields.items():
            ann = getattr(f, "annotation", Any)
            yield name, f, ann
    else:  # v1
        for name, f in model.__fields__.items():
            ann = getattr(f, "outer_type_", getattr(f, "type_", Any))
            yield name, f, ann

def field_meta(field_obj):
    """
    Return (type_str, required, default, description) for a Pydantic field (v1 or v2).
    """
    # ---- v2 (FieldInfo) ----
    if hasattr(field_obj, "is_required"):  # good discriminator for v2 FieldInfo
        ann = getattr(field_obj, "annotation", Any)
        required = bool(field_obj.is_required())
        default = None if required else getattr(field_obj, "default", None)
        desc = getattr(field_obj, "description", None)
        return (format_type(ann), required, default, desc)

    # ---- v1 (ModelField) ----
    ann = getattr(field_obj, "outer_type_", getattr(field_obj, "type_", Any))
    required = bool(getattr(field_obj, "required", False))
    default = None if required else getattr(field_obj, "default", None)
    fi = getattr(field_obj, "field_info", None)
    desc = getattr(fi, "description", None) if fi else None
    return (format_type(ann), required, default, desc)

# ------------------------------------------------------------------------------------
# Typing printers and model extraction from annotations
# ------------------------------------------------------------------------------------

def _qualname(tp: Any) -> str:
    if tp is None:
        return "None"
    if isinstance(tp, type):
        return tp.__name__
    mod = getattr(tp, "__module__", "")
    name = getattr(tp, "__name__", repr(tp))
    if mod and mod != "builtins":
        return f"{mod}.{name}"
    return name

def format_type(annotation: Any) -> str:
    origin = get_origin(annotation)
    args = get_args(annotation)

    if isinstance(annotation, str):
        return annotation

    if origin is None:
        return _qualname(annotation)

    # containers
    if origin in (list, List):
        return f"List[{format_type(args[0])}]" if args else "List[Any]"
    if origin in (tuple, Tuple):
        inner = ", ".join(format_type(a) for a in args)
        return f"Tuple[{inner}]"
    if origin in (dict, Dict):
        if len(args) == 2:
            return f"Dict[{format_type(args[0])}, {format_type(args[1])}]"
        return "Dict[Any, Any]"

    # Union / Optional
    union_type = getattr(types, "UnionType", None) or Union
    if origin is union_type:
        if args and type(None) in args:
            non_none = [a for a in args if a is not type(None)]
            return (
                f"Optional[{format_type(non_none[0])}]"
                if len(non_none) == 1
                else f"Optional[Union[{', '.join(format_type(a) for a in non_none)}]]"
            )
        return f"Union[{', '.join(format_type(a) for a in args)}]"

    # Literal
    if str(origin).endswith("Literal"):
        return f"Literal[{', '.join(repr(a) for a in args)}]"

    return _qualname(annotation)

def _collect_model_types_from_annotation(tp: Any, out: Set[type]) -> None:
    """
    Recursively collect BaseModel subclasses referenced by typing annotations.
    Handles containers and unions.
    """
    if tp is None or tp is Any:
        return

    # ForwardRef strings stay as str; Pydantic will usually resolve at model build time.
    if isinstance(tp, str):
        return

    if is_pydantic_model(tp):
        out.add(tp)
        return

    origin = get_origin(tp)
    args = get_args(tp)

    if origin is None:
        # Could be a plain class (non-typing), nothing to do.
        return

    for a in args:
        _collect_model_types_from_annotation(a, out)

def find_referenced_models(root: type) -> List[type]:
    """
    Walk fields of `root` recursively to find all referenced Pydantic models.
    Includes the root itself. Avoids cycles.
    """
    # Ensure forward refs are resolved (esp. pydantic v2)
    try:
        if hasattr(root, "model_rebuild"):
            root.model_rebuild()
    except Exception:
        pass

    discovered: Set[type] = set()
    queue: List[type] = [root]

    while queue:
        model = queue.pop()
        if model in discovered:
            continue
        discovered.add(model)

        # Resolve forward refs on each model we encounter
        try:
            if hasattr(model, "model_rebuild"):
                model.model_rebuild()
        except Exception:
            pass

        for _name, field_obj, ann in iter_model_fields(model):
            # collect nested models from the field annotation
            nested: Set[type] = set()
            _collect_model_types_from_annotation(ann, nested)

            # Also handle Pydantic's Json, conlist, constr, etc. (already covered by get_origin/args in most cases)
            for m in nested:
                if m not in discovered:
                    queue.append(m)

    # Return in a stable order: root first, then alphabetical by name
    ordered = [root] + sorted([m for m in discovered if m is not root], key=lambda c: (c.__module__, c.__name__))
    return ordered

# ------------------------------------------------------------------------------------
# Markdown generation
# ------------------------------------------------------------------------------------

def md_escape(text: Any) -> str:
    if text is None:
        return ""
    return str(text).replace("|", "\\|").replace("\n", "<br>")

def render_model_section(model: type) -> str:
    buf = io.StringIO()
    qualname = f"{model.__module__}.{model.__name__}"

    print(f"## `{model.__name__}`", file=buf)
    print("", file=buf)
    if model.__doc__:
        print(md_escape(inspect.cleandoc(model.__doc__)), file=buf)
        print("", file=buf)
    print(f"**Qualified name:** `{qualname}`", file=buf)
    print("", file=buf)

    print("| Field | Type | Required | Default | Description |", file=buf)
    print("|------:|------|:-------:|---------|-------------|", file=buf)

    for name, field_obj, ann in iter_model_fields(model):
        typ_str, required, default, desc = field_meta(field_obj)
        print(
            f"| `{name}` | `{md_escape(typ_str)}` | {('✔️' if required else '—')} | "
            f"{'—' if required or default is None else f'`{md_escape(default)}`'} | "
            f"{md_escape(desc)} |",
            file=buf,
        )

    print("", file=buf)

    # Collapsible JSON Schema (v1/v2)
    try:
        schema = model.model_json_schema() if hasattr(model, "model_json_schema") else model.schema()
        print("<details><summary>JSON Schema</summary>\n\n```json", file=buf)
        print(json.dumps(schema, indent=2, ensure_ascii=False), file=buf)
        print("```\n</details>\n", file=buf)
    except Exception:
        pass

    return buf.getvalue()

def build_markdown(models: List[type], title: str) -> str:
    header = (
        f"# {title}\n\n"
        f"_Auto-generated reference for `{models[0].__module__}.{models[0].__name__}` "
        f"and nested Pydantic models._\n\n"
        f"Models found: {len(models)}\n\n---\n\n"
    )
    body = "".join(render_model_section(m) for m in models)
    return header + body

# ------------------------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------------------------

def main():
    if MAIN_MODEL is None or not is_pydantic_model(MAIN_MODEL):
        print(
            "Edit the import near the top of this file to import your main model, e.g.\n"
            "  from myapp.models import RootModel as MAIN_MODEL",
            file=sys.stderr,
        )
        sys.exit(1)

    ap = argparse.ArgumentParser(description="Export main Pydantic model and its nested models to Markdown.")
    ap.add_argument("--out", "-o", default="pydantic_models.md", help="Output Markdown file.")
    ap.add_argument("--title", "-t", default="Pydantic Model Reference", help="Document title.")
    args = ap.parse_args()

    models = find_referenced_models(MAIN_MODEL)
    md = build_markdown(models, args.title)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(md)

    print(f"Wrote {len(models)} models to {args.out}")

if __name__ == "__main__":
    main()
