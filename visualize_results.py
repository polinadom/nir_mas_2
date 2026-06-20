"""
ВИЗУАЛИЗАЦИЯ РЕЗУЛЬТАТОВ ОТКАЗОУСТОЙЧИВОСТИ MAS
================================================

Читает все эксперименты из папки experiments/ и строит графики,
сводную CSV-таблицу и HTML-отчёт.

Запуск:
    python visualize_results.py
    python visualize_results.py --experiments experiments --out reports

Результат (по умолчанию папка reports/):
    reports/heatmap_degradation.png   - тепловая карта падения качества
    reports/bars_by_bugtype.png       - падение качества по типам багов и уровням
    reports/robustness_share.png      - доля устойчивых/уязвимых ответов
    reports/quality_baseline_vs_bug.png - качество baseline vs баговый промпт
    reports/summary.csv               - сводная таблица (для статьи)
    reports/report.html               - HTML-отчёт со всеми графиками
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

BUG_TYPES = ["incomplete", "noise", "contradiction"]
LEVELS = ["low", "medium", "high"]

BUG_TYPE_RU = {
    "incomplete": "Неполнота",
    "noise": "Шум",
    "contradiction": "Противоречие",
}
LEVEL_RU = {"low": "Низкий", "medium": "Средний", "high": "Высокий"}

# Пороги устойчивости (в % падения качества)
ROBUST_THRESHOLD = 20.0      # < 20%  -> устойчива
VULNERABLE_THRESHOLD = 50.0  # > 50%  -> уязвима


# ============================================================
# ЗАГРУЗКА И АГРЕГАЦИЯ ДАННЫХ
# ============================================================

def load_records(experiments_dir: Path) -> list[dict]:
    """Загружает все баговые эксперименты (не baseline) с метрикой падения."""
    records: list[dict] = []

    if not experiments_dir.exists():
        raise SystemExit(f"ОШИБКА: папка {experiments_dir} не найдена.")

    for json_file in sorted(experiments_dir.glob("*.json")):
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue

        bug_type = data.get("bug_type")
        if bug_type not in BUG_TYPES:
            continue  # пропускаем baseline (bug_type == "none") и мусор
        if "quality_loss_percent" not in data:
            continue

        task_id = data.get("task_id")
        if not task_id and isinstance(data.get("task"), dict):
            task_id = data["task"].get("id")

        records.append({
            "file": json_file.name,
            "task_id": task_id or "unknown",
            "bug_type": bug_type,
            "intensity": data.get("intensity", "unknown"),
            "loss": float(data.get("quality_loss_percent", 0.0)),
            "is_robust": bool(data.get("is_robust", False)),
            "baseline_quality": float(data.get("baseline_quality", 0.0) or 0.0),
            "buggy_quality": float(data.get("buggy_quality", 0.0) or 0.0),
            "success": bool(data.get("success", False)),
        })

    return records


def aggregate_loss(records: list[dict]) -> dict[tuple[str, str], float]:
    """Средний % падения качества по (тип бага, уровень)."""
    buckets: dict[tuple[str, str], list[float]] = defaultdict(list)
    for r in records:
        buckets[(r["bug_type"], r["intensity"])].append(r["loss"])
    return {key: sum(v) / len(v) for key, v in buckets.items() if v}


def robustness_breakdown(records: list[dict]) -> dict[str, dict[str, int]]:
    """Считает кол-во устойчивых / средних / уязвимых ответов по типу бага."""
    out: dict[str, dict[str, int]] = {
        bt: {"robust": 0, "medium": 0, "vulnerable": 0} for bt in BUG_TYPES
    }
    for r in records:
        bt = r["bug_type"]
        if r["loss"] < ROBUST_THRESHOLD:
            out[bt]["robust"] += 1
        elif r["loss"] <= VULNERABLE_THRESHOLD:
            out[bt]["medium"] += 1
        else:
            out[bt]["vulnerable"] += 1
    return out


def quality_by_bugtype(records: list[dict]) -> dict[str, tuple[float, float]]:
    """Среднее качество baseline и багового ответа по типу бага."""
    base: dict[str, list[float]] = defaultdict(list)
    bug: dict[str, list[float]] = defaultdict(list)
    for r in records:
        base[r["bug_type"]].append(r["baseline_quality"])
        bug[r["bug_type"]].append(r["buggy_quality"])
    return {
        bt: (
            sum(base[bt]) / len(base[bt]) if base[bt] else 0.0,
            sum(bug[bt]) / len(bug[bt]) if bug[bt] else 0.0,
        )
        for bt in BUG_TYPES
    }


# ============================================================
# ПОСТРОЕНИЕ ГРАФИКОВ
# ============================================================

def color_for_loss(loss: float) -> str:
    if loss < ROBUST_THRESHOLD:
        return "#2e7d32"  # зелёный
    if loss <= VULNERABLE_THRESHOLD:
        return "#f9a825"  # жёлтый
    return "#c62828"      # красный


def plot_heatmap(loss_table, out_dir: Path):
    import matplotlib.pyplot as plt
    import numpy as np

    matrix = np.full((len(BUG_TYPES), len(LEVELS)), np.nan)
    for i, bt in enumerate(BUG_TYPES):
        for j, lvl in enumerate(LEVELS):
            if (bt, lvl) in loss_table:
                matrix[i, j] = loss_table[(bt, lvl)]

    fig, ax = plt.subplots(figsize=(7, 5))
    im = ax.imshow(matrix, cmap="RdYlGn_r", vmin=0, vmax=100, aspect="auto")

    ax.set_xticks(range(len(LEVELS)))
    ax.set_xticklabels([LEVEL_RU[l] for l in LEVELS])
    ax.set_yticks(range(len(BUG_TYPES)))
    ax.set_yticklabels([BUG_TYPE_RU[b] for b in BUG_TYPES])
    ax.set_xlabel("Уровень повреждения")
    ax.set_ylabel("Тип бага")
    ax.set_title("Среднее падение качества (%)\nпо типу бага и уровню повреждения")

    for i in range(len(BUG_TYPES)):
        for j in range(len(LEVELS)):
            val = matrix[i, j]
            if not np.isnan(val):
                ax.text(j, i, f"{val:.1f}%", ha="center", va="center",
                        color="black", fontweight="bold")

    cbar = fig.colorbar(im, ax=ax)
    cbar.set_label("% падения качества")
    fig.tight_layout()
    path = out_dir / "heatmap_degradation.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def plot_bars_by_bugtype(loss_table, out_dir: Path):
    import matplotlib.pyplot as plt
    import numpy as np

    x = np.arange(len(LEVELS))
    width = 0.25
    fig, ax = plt.subplots(figsize=(8, 5))

    for k, bt in enumerate(BUG_TYPES):
        vals = [loss_table.get((bt, lvl), 0.0) for lvl in LEVELS]
        ax.bar(x + (k - 1) * width, vals, width, label=BUG_TYPE_RU[bt])

    ax.axhline(ROBUST_THRESHOLD, color="#2e7d32", linestyle="--", linewidth=1,
               label=f"порог устойчивости ({ROBUST_THRESHOLD:.0f}%)")
    ax.axhline(VULNERABLE_THRESHOLD, color="#c62828", linestyle="--", linewidth=1,
               label=f"порог уязвимости ({VULNERABLE_THRESHOLD:.0f}%)")

    ax.set_xticks(x)
    ax.set_xticklabels([LEVEL_RU[l] for l in LEVELS])
    ax.set_xlabel("Уровень повреждения")
    ax.set_ylabel("Среднее падение качества (%)")
    ax.set_title("Падение качества MAS по типам багов и уровням")
    ax.legend(fontsize=8)
    fig.tight_layout()
    path = out_dir / "bars_by_bugtype.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def plot_robustness_share(breakdown, out_dir: Path):
    import matplotlib.pyplot as plt
    import numpy as np

    labels = [BUG_TYPE_RU[b] for b in BUG_TYPES]
    robust = [breakdown[b]["robust"] for b in BUG_TYPES]
    medium = [breakdown[b]["medium"] for b in BUG_TYPES]
    vuln = [breakdown[b]["vulnerable"] for b in BUG_TYPES]

    x = np.arange(len(BUG_TYPES))
    fig, ax = plt.subplots(figsize=(8, 5))

    ax.bar(x, robust, label="Устойчива (<20%)", color="#2e7d32")
    ax.bar(x, medium, bottom=robust, label="Средне (20-50%)", color="#f9a825")
    bottom2 = [r + m for r, m in zip(robust, medium)]
    ax.bar(x, vuln, bottom=bottom2, label="Уязвима (>50%)", color="#c62828")

    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylabel("Количество экспериментов")
    ax.set_title("Распределение устойчивости ответов MAS по типам багов")
    ax.legend(fontsize=8)
    fig.tight_layout()
    path = out_dir / "robustness_share.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def plot_quality_baseline_vs_bug(quality, out_dir: Path):
    import matplotlib.pyplot as plt
    import numpy as np

    x = np.arange(len(BUG_TYPES))
    width = 0.35
    fig, ax = plt.subplots(figsize=(8, 5))

    base_vals = [quality[b][0] * 100 for b in BUG_TYPES]
    bug_vals = [quality[b][1] * 100 for b in BUG_TYPES]

    ax.bar(x - width / 2, base_vals, width, label="Baseline (чистый промпт)",
           color="#1565c0")
    ax.bar(x + width / 2, bug_vals, width, label="Баговый промпт",
           color="#ef6c00")

    ax.set_xticks(x)
    ax.set_xticklabels([BUG_TYPE_RU[b] for b in BUG_TYPES])
    ax.set_ylabel("Среднее качество (%)")
    ax.set_ylim(0, 100)
    ax.set_title("Качество ответов: baseline vs баговый промпт")
    ax.legend(fontsize=8)
    fig.tight_layout()
    path = out_dir / "quality_baseline_vs_bug.png"
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


# ============================================================
# CSV И HTML ОТЧЁТЫ
# ============================================================

def write_csv(loss_table, records, out_dir: Path) -> Path:
    path = out_dir / "summary.csv"
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["bug_type", "level", "avg_loss_percent", "n_experiments"])
        counts: dict[tuple[str, str], int] = defaultdict(int)
        for r in records:
            counts[(r["bug_type"], r["intensity"])] += 1
        for bt in BUG_TYPES:
            for lvl in LEVELS:
                if (bt, lvl) in loss_table:
                    writer.writerow([
                        bt, lvl, f"{loss_table[(bt, lvl)]:.1f}", counts[(bt, lvl)]
                    ])
    return path


def write_html(loss_table, records, images, out_dir: Path) -> Path:
    total = len(records)
    success = sum(1 for r in records if r["success"])
    success_rate = (success / total * 100) if total else 0.0

    rows = []
    for bt in BUG_TYPES:
        cells = [f"<td><b>{BUG_TYPE_RU[bt]}</b></td>"]
        for lvl in LEVELS:
            if (bt, lvl) in loss_table:
                val = loss_table[(bt, lvl)]
                color = color_for_loss(val)
                cells.append(
                    f'<td style="background:{color};color:#fff;text-align:center">'
                    f"{val:.1f}%</td>"
                )
            else:
                cells.append('<td style="text-align:center">—</td>')
        rows.append("<tr>" + "".join(cells) + "</tr>")

    table_html = "\n".join(rows)
    img_html = "\n".join(
        f'<div class="card"><img src="{img.name}" alt="{img.name}"></div>'
        for img in images
    )

    html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="utf-8">
<title>Отчёт об отказоустойчивости MAS</title>
<style>
  body {{ font-family: Segoe UI, Arial, sans-serif; margin: 32px; color: #1a1a1a; }}
  h1 {{ font-size: 22px; }}
  .stats {{ display: flex; gap: 16px; margin: 16px 0; flex-wrap: wrap; }}
  .stat {{ background: #f3f4f6; border-radius: 10px; padding: 14px 20px; }}
  .stat b {{ font-size: 22px; display: block; }}
  table {{ border-collapse: collapse; margin: 16px 0; }}
  td, th {{ border: 1px solid #ddd; padding: 8px 14px; }}
  .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-top: 20px; }}
  .card img {{ width: 100%; border: 1px solid #eee; border-radius: 10px; }}
  .legend span {{ display:inline-block; padding:2px 8px; border-radius:6px; color:#fff; margin-right:8px; }}
</style>
</head>
<body>
  <h1>Тестирование отказоустойчивости мультиагентной системы</h1>
  <p>в условиях неполной, противоречивой и шумной информации</p>

  <div class="stats">
    <div class="stat"><b>{total}</b>баговых экспериментов</div>
    <div class="stat"><b>{success_rate:.0f}%</b>успешных запусков MAS</div>
    <div class="stat"><b>{len(set(r['task_id'] for r in records))}</b>уникальных задач</div>
  </div>

  <h2>Сводная таблица падения качества (%)</h2>
  <table>
    <tr><th>Тип бага</th><th>Низкий</th><th>Средний</th><th>Высокий</th></tr>
    {table_html}
  </table>
  <p class="legend">
    <span style="background:#2e7d32">&lt; 20% — устойчива</span>
    <span style="background:#f9a825">20–50% — средняя уязвимость</span>
    <span style="background:#c62828">&gt; 50% — уязвима</span>
  </p>

  <h2>Графики</h2>
  <div class="grid">
    {img_html}
  </div>
</body>
</html>
"""
    path = out_dir / "report.html"
    path.write_text(html, encoding="utf-8")
    return path


def print_table(loss_table, records):
    print("=" * 60)
    print("СВОДНАЯ ТАБЛИЦА ПАДЕНИЯ КАЧЕСТВА (%)")
    print("=" * 60)
    print(f"{'Тип бага':<16}{'Low':>10}{'Medium':>10}{'High':>10}")
    print("-" * 46)
    for bt in BUG_TYPES:
        row = f"{BUG_TYPE_RU[bt]:<16}"
        for lvl in LEVELS:
            if (bt, lvl) in loss_table:
                row += f"{loss_table[(bt, lvl)]:>9.1f}%"
            else:
                row += f"{'—':>10}"
        print(row)
    print("-" * 46)
    print(f"Всего баговых экспериментов: {len(records)}")


# ============================================================
# MAIN
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="Визуализация результатов отказоустойчивости MAS")
    parser.add_argument("--experiments", default="experiments", help="папка с результатами")
    parser.add_argument("--out", default="reports", help="папка для отчётов и графиков")
    args = parser.parse_args()

    experiments_dir = Path(args.experiments)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    records = load_records(experiments_dir)
    if not records:
        raise SystemExit(
            f"В папке {experiments_dir} нет баговых экспериментов. "
            f"Сначала запустите: python run_experiments.py"
        )

    loss_table = aggregate_loss(records)
    breakdown = robustness_breakdown(records)
    quality = quality_by_bugtype(records)

    print_table(loss_table, records)

    # CSV (не требует matplotlib)
    csv_path = write_csv(loss_table, records, out_dir)
    print(f"\nCSV сохранён: {csv_path}")

    try:
        import matplotlib
        matplotlib.use("Agg")
    except ImportError:
        print(
            "\n[!] matplotlib не установлен — графики пропущены.\n"
            "    Установите: pip install matplotlib\n"
            f"    Текстовая сводка и {csv_path.name} уже готовы."
        )
        return

    images = [
        plot_heatmap(loss_table, out_dir),
        plot_bars_by_bugtype(loss_table, out_dir),
        plot_robustness_share(breakdown, out_dir),
        plot_quality_baseline_vs_bug(quality, out_dir),
    ]
    html_path = write_html(loss_table, records, images, out_dir)

    print("\nГрафики сохранены:")
    for img in images:
        print(f"  - {img}")
    print(f"\nHTML-отчёт: {html_path}")
    print("\nГотово. Откройте report.html в браузере для демонстрации на защите.")


if __name__ == "__main__":
    main()
