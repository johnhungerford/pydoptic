"""
Benchmark comparing pydoptic's BaseModel with pydantic's BaseModel.

Measures:
  1. Model construction (instantiating a 15-field model with a 5-level-deep
     nested chain, including list/set/dict collections)
  2. Field access (top-level scalar field, top-level collection field, and a
     field reached by traversing all 5 levels of nesting)

Run with:
    python benchmarks/bench_model.py [--iterations N] [--repeat N]
"""
import argparse
import gc
import os
import statistics
import sys
import timeit
from datetime import date
from typing import Dict, List, Set

# pydoptic's BaseModelMeta and BaseModel.__init__ currently contain stray
# debug `print()` calls (see src/pydoptic/base_model.py) that fire on every
# class definition and on every construction of a model with a nested
# BaseModel field. They are part of what's being measured (a real cost paid
# today), but they'd otherwise spam stdout, so redirect module output to
# devnull (even during import) until results are ready to print.
_REAL_STDOUT = sys.stdout
sys.stdout = open(os.devnull, "w")

import pydoptic as pd_optic
import pydantic as pd_antic


# --------------------------------------------------------------------------
# pydoptic models: Root -> Level1 -> Level2 -> Level3 -> Level4 -> Level5
# (5 levels of nesting below Root), with list/set/dict collections along
# the way.
# --------------------------------------------------------------------------

class OpticLevel5(pd_optic.BaseModel):
    code: pd_optic.Prop['OpticLevel5', str]
    weight: pd_optic.Prop['OpticLevel5', float]


class OpticLevel4(pd_optic.BaseModel):
    id: pd_optic.Prop['OpticLevel4', int]
    level5: pd_optic.Prop['OpticLevel4', OpticLevel5]
    scores: pd_optic.PropArr['OpticLevel4', float]


class OpticLevel3(pd_optic.BaseModel):
    name: pd_optic.Prop['OpticLevel3', str]
    level4: pd_optic.Prop['OpticLevel3', OpticLevel4]
    labels: pd_optic.Prop['OpticLevel3', set]


class OpticLevel2(pd_optic.BaseModel):
    title: pd_optic.Prop['OpticLevel2', str]
    level3: pd_optic.Prop['OpticLevel2', OpticLevel3]
    count: pd_optic.Prop['OpticLevel2', int]


class OpticLevel1(pd_optic.BaseModel):
    key: pd_optic.Prop['OpticLevel1', str]
    level2: pd_optic.Prop['OpticLevel1', OpticLevel2]
    active: pd_optic.Prop['OpticLevel1', bool]


class OpticRoot(pd_optic.BaseModel):
    id: pd_optic.Prop['OpticRoot', int]
    name: pd_optic.Prop['OpticRoot', str]
    email: pd_optic.Prop['OpticRoot', str]
    age: pd_optic.Prop['OpticRoot', int]
    score: pd_optic.Prop['OpticRoot', float]
    is_active: pd_optic.Prop['OpticRoot', bool]
    created_at: pd_optic.Prop['OpticRoot', date]
    tags: pd_optic.PropArr['OpticRoot', str]
    aliases: pd_optic.Prop['OpticRoot', set]
    metadata: pd_optic.Prop['OpticRoot', dict]
    scores_history: pd_optic.PropArr['OpticRoot', float]
    rating: pd_optic.Prop['OpticRoot', float]
    nested: pd_optic.Prop['OpticRoot', OpticLevel1]
    is_verified: pd_optic.Prop['OpticRoot', bool]
    balance: pd_optic.Prop['OpticRoot', float]


# --------------------------------------------------------------------------
# pydantic equivalent
# --------------------------------------------------------------------------

class PydLevel5(pd_antic.BaseModel):
    code: str
    weight: float


class PydLevel4(pd_antic.BaseModel):
    id: int
    level5: PydLevel5
    scores: List[float]


class PydLevel3(pd_antic.BaseModel):
    name: str
    level4: PydLevel4
    labels: Set[str]


class PydLevel2(pd_antic.BaseModel):
    title: str
    level3: PydLevel3
    count: int


class PydLevel1(pd_antic.BaseModel):
    key: str
    level2: PydLevel2
    active: bool


class PydRoot(pd_antic.BaseModel):
    id: int
    name: str
    email: str
    age: int
    score: float
    is_active: bool
    created_at: date
    tags: List[str]
    aliases: Set[str]
    metadata: Dict[str, str]
    scores_history: List[float]
    rating: float
    nested: PydLevel1
    is_verified: bool
    balance: float


# --------------------------------------------------------------------------
# Sample data
# --------------------------------------------------------------------------

def make_kwargs() -> dict:
    return dict(
        id=42,
        name="Ada Lovelace",
        email="ada@example.com",
        age=36,
        score=98.6,
        is_active=True,
        created_at=date(2024, 1, 1),
        tags=["engineer", "mathematician", "pioneer"],
        aliases={"ada", "augusta"},
        metadata={"team": "core", "level": "senior"},
        scores_history=[1.0, 2.5, 3.75, 4.0],
        rating=4.9,
        nested=dict(
            key="lvl1",
            active=True,
            level2=dict(
                title="lvl2",
                count=7,
                level3=dict(
                    name="lvl3",
                    labels={"a", "b", "c"},
                    level4=dict(
                        id=99,
                        scores=[0.1, 0.2, 0.3],
                        level5=dict(
                            code="lvl5",
                            weight=1.23,
                        ),
                    ),
                ),
            ),
        ),
        is_verified=False,
        balance=1000.50,
    )


def build_optic_kwargs() -> dict:
    kwargs = make_kwargs()
    kwargs["nested"] = OpticLevel1(
        key="lvl1",
        active=True,
        level2=OpticLevel2(
            title="lvl2",
            count=7,
            level3=OpticLevel3(
                name="lvl3",
                labels={"a", "b", "c"},
                level4=OpticLevel4(
                    id=99,
                    scores=[0.1, 0.2, 0.3],
                    level5=OpticLevel5(code="lvl5", weight=1.23),
                ),
            ),
        ),
    )
    return kwargs


OPTIC_KWARGS = build_optic_kwargs()
PYDANTIC_KWARGS = make_kwargs()

OPTIC_INSTANCE = OpticRoot(**OPTIC_KWARGS)
PYDANTIC_INSTANCE = PydRoot(**PYDANTIC_KWARGS)

# Pre-composed selector for the 5-level-deep field, as a caller would define
# it once and reuse it (rather than re-composing it on every access).
OPTIC_DEEP_SELECT = OpticRoot.nested(OpticLevel1.level2)(OpticLevel2.level3)(OpticLevel3.level4)(OpticLevel4.level5)(OpticLevel5.code)


def construct_optic():
    return OpticRoot(**OPTIC_KWARGS)


def construct_pydantic():
    return PydRoot(**PYDANTIC_KWARGS)


def access_optic_scalar():
    return OpticRoot.name.get_val(OPTIC_INSTANCE)


def access_optic_scalar_attr():
    return OPTIC_INSTANCE.name


def access_pydantic_scalar():
    return PYDANTIC_INSTANCE.name


def access_optic_collection():
    return OpticRoot.tags.get_val(OPTIC_INSTANCE)


def access_pydantic_collection():
    return PYDANTIC_INSTANCE.tags


def access_optic_deep():
    return OPTIC_DEEP_SELECT.get(OPTIC_INSTANCE).value


def access_optic_deep_attr():
    return OPTIC_INSTANCE.nested.level2.level3.level4.level5.code


def access_pydantic_deep():
    return PYDANTIC_INSTANCE.nested.level2.level3.level4.level5.code


BENCHMARKS = [
    ("construction", "pydoptic", construct_optic),
    ("construction", "pydantic", construct_pydantic),
    ("scalar field access (get_val)", "pydoptic", access_optic_scalar),
    ("scalar field access (attr)", "pydoptic", access_optic_scalar_attr),
    ("scalar field access", "pydantic", access_pydantic_scalar),
    ("collection field access (get_val)", "pydoptic", access_optic_collection),
    ("collection field access", "pydantic", access_pydantic_collection),
    ("5-level nested field access (select)", "pydoptic", access_optic_deep),
    ("5-level nested field access (attr)", "pydoptic", access_optic_deep_attr),
    ("5-level nested field access", "pydantic", access_pydantic_deep),
]


def run(iterations: int, repeat: int):
    gc.disable()
    results = []
    for label, lib, fn in BENCHMARKS:
        timer = timeit.Timer(fn)
        samples = timer.repeat(repeat=repeat, number=iterations)
        per_call = [s / iterations for s in samples]
        best = min(per_call)
        med = statistics.median(per_call)
        results.append((label, lib, best, med))
    gc.enable()
    return results


def print_results(results, iterations: int, repeat: int):
    print(f"iterations={iterations} repeat={repeat}\n")
    header = f"{'benchmark':<38} {'library':<10} {'best (us)':>12} {'median (us)':>13}"
    print(header)
    print("-" * len(header))
    grouped = {}
    for label, lib, best, med in results:
        grouped.setdefault(label, []).append((lib, best, med))

    for label, rows in grouped.items():
        for lib, best, med in rows:
            print(f"{label:<38} {lib:<10} {best * 1e6:>12.3f} {med * 1e6:>13.3f}")
        if len(rows) == 2:
            (_, best_a, _), (_, best_b, _) = rows
            slower, faster = (rows[0], rows[1]) if best_a > best_b else (rows[1], rows[0])
            ratio = slower[1] / faster[1] if faster[1] > 0 else float('inf')
            print(f"{'':<38} {'':<10} {'':>12} {f'{slower[0]} is {ratio:.1f}x slower than {faster[0]}':>13}")
        print()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iterations", type=int, default=20_000, help="calls per timing sample")
    parser.add_argument("--repeat", type=int, default=5, help="number of timing samples")
    args = parser.parse_args()

    results = run(args.iterations, args.repeat)
    sys.stdout = _REAL_STDOUT
    print_results(results, args.iterations, args.repeat)


if __name__ == "__main__":
    main()
