"""Esperimento di cell repair (Hospital dirty/clean) con Llama 3.1 + retrieval.
Supporta il dataset originale e le 4 perturbazioni (p1_, p2_, p3_, p4_) da protocollo.

Esecuzione:
    python3 test_hospital.py --dry-run
    python3 test_hospital.py --prefix p1_
    python3 test_hospital.py --prefix p2_
    python3 test_hospital.py --prefix p3_
    python3 test_hospital.py --prefix p4_
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from pydantic import BaseModel
from tqdm import tqdm

# ============================= CONFIGURAZIONE =============================
MODEL_NAME = "llama3.1:8b"
MAX_ROWS = 200               # Righe CON errori; 0 = tutte
K_CONTEXT_ROWS = 3
NUM_THREADS = 6
SEED = 42

HERE = Path(__file__).resolve().parent

CLEAN_TO_DIRTY = {
    "index": "index",
    "ProviderNumber": "provider_number",
    "HospitalName": "name",
    "Address1": "address_1",
    "Address2": "address_2",
    "Address3": "address_3",
    "City": "city",
    "State": "state",
    "ZipCode": "zip",
    "CountyName": "county",
    "PhoneNumber": "phone",
    "HospitalType": "type",
    "HospitalOwner": "owner",
    "EmergencyService": "emergency_service",
    "Condition": "condition",
    "MeasureCode": "measure_code",
    "MeasureName": "measure_name",
    "Score": "score",
    "Sample": "sample",
    "Stateavg": "state_average",
}

# Mappa usata in P4 (Perturbazione superficiale: ridenominazione colonne)
P4_RENAME_MAP = {
    "index": "index",
    "provider_number": "col_01",
    "name": "col_02",
    "address_1": "col_03",
    "address_2": "col_04",
    "address_3": "col_05",
    "city": "col_06",
    "state": "col_07",
    "zip": "col_08",
    "county": "col_09",
    "phone": "col_10",
    "type": "col_11",
    "owner": "col_12",
    "emergency_service": "col_13",
    "condition": "col_14",
    "measure_code": "col_15",
    "measure_name": "col_16",
    "score": "col_17",
    "sample": "col_18",
    "state_average": "col_19",
}
P4_INV_MAP = {v: k for k, v in P4_RENAME_MAP.items()}

# Solo le 15 colonne governate da Dipendenze Funzionali (FD).
FD_REPAIR_COLS = [
    "provider_number", "name", "address_1", "city", "state", "zip",
    "county", "phone", "type", "owner", "emergency_service",
    "condition", "measure_code", "measure_name", "state_average",
]
NON_FD_COLS = ["score", "sample"]

MEASURE_BLOCK_COLS = {"condition", "measure_code", "measure_name", "state_average"}

# Pesi FD-aware con state_average valorizzato a 8.
BASE_WEIGHTS = {
    "provider_number": 9, "name": 8, "measure_code": 8, "state_average": 8,
    "phone": 7, "address_1": 7, "zip": 6, "measure_name": 6,
    "city": 4, "condition": 4, "county": 3, "owner": 2,
    "state": 2, "type": 1, "emergency_service": 1,
}

LOG_COLUMNS = [
    "row_id", "column", "logical_column", "valore_sporco", "ground_truth",
    "pred_con_contesto", "pred_senza_contesto", "context_row_ids",
    "context_target_values", "context_has_answer",
    "exact_con_contesto", "exact_senza_contesto",
    "normalized_con_contesto", "normalized_senza_contesto",
    "esito", "errore_modello_con", "errore_modello_senza",
]


class CellRepair(BaseModel):
    repaired_value: str


def resolve_paths(prefix: str) -> tuple[Path, Path, Path, Path, Path]:
    data_dir = HERE / "db" if (HERE / "db").exists() else HERE
    dirty_csv = data_dir / f"{prefix}dirty.csv"
    clean_csv = data_dir / f"{prefix}clean.csv"
    if not dirty_csv.is_file() and (HERE / f"{prefix}dirty.csv").is_file():
        data_dir = HERE
        dirty_csv = data_dir / f"{prefix}dirty.csv"
        clean_csv = data_dir / f"{prefix}clean.csv"
    output_log = data_dir / f"{prefix}hospital_output_log.csv"
    output_repaired = data_dir / f"{prefix}hospital_output_repaired.csv"
    return data_dir, dirty_csv, clean_csv, output_log, output_repaired


def load_data(dirty_csv: Path, clean_csv: Path) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, str]]:
    if not dirty_csv.is_file() or not clean_csv.is_file():
        raise FileNotFoundError(f"File mancanti: {dirty_csv} e/o {clean_csv}.")

    dirty = pd.read_csv(dirty_csv, dtype=str, keep_default_na=False)
    clean = pd.read_csv(clean_csv, dtype=str, keep_default_na=False)
    dirty.columns = dirty.columns.str.strip()
    clean.columns = clean.columns.str.strip()

    # Gestione trasparente sia dello schema standard sia dello schema P4 (colonne rinominate e permutate)
    if set(dirty.columns) == set(P4_RENAME_MAP.values()):
        # In P4 preserviamo l'ordine permutato delle colonne presente nel CSV!
        col_order = list(dirty.columns)
        clean = clean[col_order].copy()
        dirty = dirty[col_order].copy()
        logical_to_actual = P4_RENAME_MAP.copy()
    else:
        if set(clean.columns) == set(CLEAN_TO_DIRTY):
            clean = clean.rename(columns=CLEAN_TO_DIRTY)
        if set(dirty.columns) != set(CLEAN_TO_DIRTY.values()):
            raise ValueError(f"Colonne dirty inattese: {list(dirty.columns)}")
        col_order = list(CLEAN_TO_DIRTY.values())
        dirty = dirty[col_order].copy()
        clean = clean[col_order].copy()
        logical_to_actual = {c: c for c in col_order}

    ids = dirty["index"].tolist()
    clean = clean.set_index("index", drop=False).loc[ids].reset_index(drop=True)
    dirty = dirty.reset_index(drop=True)

    dirty = dirty.apply(lambda s: s.str.strip())
    clean = clean.apply(lambda s: s.str.strip())
    mask = dirty.ne(clean)

    print(f"Dirty: {dirty_csv} ({len(dirty)} righe)")
    print(f"Clean: {clean_csv} ({len(clean)} righe)")
    print(f"Totale celle differenti: {int(mask.to_numpy().sum())}")
    return dirty, clean, logical_to_actual


def get_context_indices(
    dirty: pd.DataFrame,
    row_idx: int,
    target_actual_col: str,
    logical_to_actual: dict[str, str],
    k: int,
) -> list[int]:
    """Retrieval FD-aware solo sul dirty (senza consultare la ground truth)."""
    actual_to_logical = {v: k for k, v in logical_to_actual.items()}
    target_logical = actual_to_logical[target_actual_col]

    query = dirty.loc[row_idx]
    scores = pd.Series(0.0, index=dirty.index)

    for logical_col, base_w in BASE_WEIGHTS.items():
        actual_col = logical_to_actual[logical_col]
        if actual_col == target_actual_col or actual_col not in dirty.columns:
            continue
        value = query[actual_col]
        if value.lower() in {"", "empty", "null", "nan", "none"}:
            continue

        weight = base_w
        if target_logical in MEASURE_BLOCK_COLS:
            if logical_col in {"measure_code", "measure_name", "state_average", "condition", "state"}:
                weight = base_w * 3.0
            else:
                weight = base_w * 0.25

        scores += weight * dirty[actual_col].eq(value).astype(float)

    scores.loc[row_idx] = -np.inf
    ranked = scores.nlargest(min(k, len(scores) - 1))
    return ranked.index[ranked > 0].tolist()


def ask_llama(
    dirty_row: dict, target_col: str, context_rows: list[dict] | None
) -> tuple[str | None, str]:
    from ollama import chat

    system_prompt = (
        "You are repairing one corrupted cell in a hospital CSV. "
        "Infer the most likely original value using the other fields and functional dependencies. "
        "Reference rows, if supplied, come from a noisy dataset and might "
        "also contain errors; use them as evidence, not as unquestionable truth. "
        "Keep exact spelling, spacing, and formatting. "
        "Output only the JSON object specified by the schema."
    )

    payload = {"target_column": target_col, "dirty_row": dirty_row}
    if context_rows:
        payload["similar_dirty_rows"] = context_rows

    try:
        response = chat(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            format=CellRepair.model_json_schema(),
            options={
                "temperature": 0.0,
                "num_predict": 128,
                "num_ctx": 4096,
                "num_thread": NUM_THREADS,
            },
            keep_alive="30m",
        )
        value = CellRepair.model_validate_json(response.message.content)
        return value.repaired_value.strip(), ""
    except Exception as exc:
        return None, f"{type(exc).__name__}: {exc}"


def norm(text: str | None) -> str:
    return "" if text is None else "".join(text.lower().split())


def run(max_rows: int, dry_run: bool, prefix: str, include_non_fd: bool) -> None:
    data_dir, dirty_csv, clean_csv, output_log, output_repaired = resolve_paths(prefix)
    dirty, clean, logical_to_actual = load_data(dirty_csv, clean_csv)
    actual_to_logical = {v: k for k, v in logical_to_actual.items()}

    logical_targets = FD_REPAIR_COLS + (NON_FD_COLS if include_non_fd else [])
    target_cols = [logical_to_actual[c] for c in logical_targets]

    target_mask = dirty[target_cols].ne(clean[target_cols])
    affected = target_mask.index[target_mask.any(axis=1)].to_numpy()

    if max_rows > 0 and len(affected) > max_rows:
        rng = np.random.default_rng(SEED)
        selected = np.sort(rng.choice(affected, size=max_rows, replace=False))
    else:
        selected = affected

    positions = [
        (int(i), col)
        for i in selected
        for col in target_cols
        if bool(target_mask.at[i, col])
    ]
    print(f"\nPrefisso attivo: {prefix!r}")
    print(f"Righe con errori nelle colonne target: {len(affected)}")
    print(f"Righe selezionate per il test: {len(selected)}")
    print(f"Celle reali da riparare: {len(positions)}")

    if dry_run:
        print("\nDRY-RUN: nessuna chiamata a Ollama; nessun file modificato.")
        for i, col in positions[:8]:
            ctx_idx = get_context_indices(dirty, i, col, logical_to_actual, K_CONTEXT_ROWS)
            ctx_vals = dirty.loc[ctx_idx, col].tolist()
            print(f"  ID {dirty.at[i, 'index']} | {col} ({actual_to_logical[col]}): "
                  f"{dirty.at[i, col]!r} -> {clean.at[i, col]!r} | ctx={ctx_vals}")
        return

    data_dir.mkdir(parents=True, exist_ok=True)
    repaired = dirty.copy()
    logs: list[dict] = []

    for i, col in tqdm(positions, desc=f"Llama 3.1 ({prefix or 'orig'}) - cell repair"):
        original = dirty.at[i, col]
        truth = clean.at[i, col]
        # Mantiene l'ordine esatto delle colonne del CSV (fondamentale per P4!)
        dirty_row = dirty.loc[i].drop(labels="index").to_dict()

        context_idx = get_context_indices(dirty, i, col, logical_to_actual, K_CONTEXT_ROWS)
        context_rows = dirty.loc[context_idx].drop(columns="index").to_dict("records")
        context_values = dirty.loc[context_idx, col].tolist()
        context_ids = dirty.loc[context_idx, "index"].tolist()

        with_ctx, error_with = ask_llama(dirty_row, col, context_rows)
        without_ctx, error_without = ask_llama(dirty_row, col, None)

        if with_ctx is not None:
            repaired.at[i, col] = with_ctx

        ok_with = int(with_ctx == truth) if with_ctx is not None else 0
        ok_without = int(without_ctx == truth) if without_ctx is not None else 0
        if ok_with and not ok_without:
            esito = "Corretto solo con contesto"
        elif ok_with and ok_without:
            esito = "Corretto in entrambi i modi"
        elif not ok_with and ok_without:
            esito = "Corretto solo senza contesto"
        else:
            esito = "Non corretto"

        logs.append({
            "row_id": dirty.at[i, "index"],
            "column": col,
            "logical_column": actual_to_logical[col],
            "valore_sporco": original,
            "ground_truth": truth,
            "pred_con_contesto": with_ctx,
            "pred_senza_contesto": without_ctx,
            "context_row_ids": " | ".join(context_ids),
            "context_target_values": " | ".join(context_values),
            "context_has_answer": int(truth in context_values),
            "exact_con_contesto": ok_with,
            "exact_senza_contesto": ok_without,
            "normalized_con_contesto": int(norm(with_ctx) == norm(truth)) if with_ctx is not None else 0,
            "normalized_senza_contesto": int(norm(without_ctx) == norm(truth)) if without_ctx is not None else 0,
            "esito": esito,
            "errore_modello_con": error_with,
            "errore_modello_senza": error_without,
        })

        if len(logs) % 5 == 0:
            pd.DataFrame(logs, columns=LOG_COLUMNS).to_csv(output_log, index=False)
            repaired.to_csv(output_repaired, index=False)

    results = pd.DataFrame(logs, columns=LOG_COLUMNS)
    results.to_csv(output_log, index=False)
    repaired.to_csv(output_repaired, index=False)

    print("\n================== RISULTATI FINALI ==================")
    print(f"Celle testate: {len(results)}")
    if len(results):
        for name, col_m in [
            ("Accuracy ESATTA con contesto", "exact_con_contesto"),
            ("Accuracy ESATTA senza contesto", "exact_senza_contesto"),
            ("Accuracy normalizzata con contesto", "normalized_con_contesto"),
            ("Accuracy normalizzata senza contesto", "normalized_senza_contesto"),
            ("Risposta presente nel contesto", "context_has_answer"),
        ]:
            print(f"{name}: {results[col_m].mean():.2%}")
        print("\nAccuracy esatta per colonna logica:")
        print((results.groupby("logical_column")[
            ["exact_con_contesto", "exact_senza_contesto", "context_has_answer"]
        ].mean() * 100).round(2).to_string())
        print("\nEsiti:")
        print(results["esito"].value_counts().to_string())
    print(f"\nLog: {output_log}")
    print(f"CSV riparato: {output_repaired}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Riparazione Hospital dirty/clean con Llama 3.1")
    parser.add_argument("--dry-run", action="store_true", help="Stampa differenze senza usare Ollama")
    parser.add_argument("--max-rows", type=int, default=MAX_ROWS,
                        help="Numero di righe CON errori da testare (0=tutte)")
    parser.add_argument("--prefix", type=str, default="",
                        help="Prefisso dei file CSV (es. 'p1_', 'p2_', 'p3_', 'p4_')")
    parser.add_argument("--include-non-fd", action="store_true",
                        help="Include anche score e sample (colonne prive di FD)")
    args = parser.parse_args()
    if args.max_rows < 0:
        parser.error("--max-rows deve essere >= 0")
    run(
        max_rows=args.max_rows,
        dry_run=args.dry_run,
        prefix=args.prefix,
        include_non_fd=args.include_non_fd,
    )