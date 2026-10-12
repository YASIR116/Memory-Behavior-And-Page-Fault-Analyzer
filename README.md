# Windows Memory Behavior and Page-Fault Analyzer

A Windows 10/11 desktop application for conducting controlled memory experiments, measuring page-fault activity, and visualizing process memory behavior.

Built with **Python 3.12**, **Streamlit**, and **Plotly**. Uses native Windows APIs (`GetProcessMemoryInfo`, `GlobalMemoryStatusEx`, `GetPerformanceInfo`) via `ctypes`.

---

## Installation

```bash
cd "windows-memory-analyzer"
pip install -r requirements.txt
```

> No administrator privileges required. No VM, cloud, or GPU needed.

---

## Launch

```bash
streamlit run app.py
```

The browser opens automatically at `http://localhost:8501`.

---

## Run Tests

```bash
cd "windows-memory-analyzer"
python -m pytest tests/ -v
```

---

## Pages

| Page | Description |
|------|-------------|
| 🖥️ Dashboard | Real-time system RAM, pagefile, CPU gauges and trend charts |
| 🔍 Process Inspector | Per-process working set, private bytes, page-fault count |
| 🧪 Memory Experiments | Five controlled workloads (A–E) with live graphs |
| 📉 Page-Fault Analysis | Detailed fault counter analysis with dual-axis charts |
| ⚖️ Experiment Comparison | Side-by-side comparison of saved experiments |
| 📚 Experiment History | View, export (CSV), and delete past experiments |
| ℹ️ About & Metrics | Windows memory concepts and counter reference |

---

## Experiments

| ID | Workload | Description |
|----|----------|-------------|
| A | Allocation | Allocate virtual memory without full page access |
| B | Sequential | Touch all pages in order (demand-zero faults) |
| C | Repeated | Multiple passes over resident pages |
| D | Random | Pseudorandom page access (configurable seed) |
| E | Release | Allocate, touch, then free — observe standby list effect |

---

## Demo Sequence (~5–7 minutes)

1. Open the **Dashboard** — observe system RAM and pagefile gauges.
2. Open **Process Inspector**, select `python.exe`, inspect working set and page-fault count.
3. Go to **Memory Experiments**, select **B – Sequential**, allocation 64 MiB, 12 s — start.
4. Watch the live working-set chart rise as pages are faulted in.
5. After completion, open **Page-Fault Analysis** — review fault delta and interpretation.
6. Run **D – Random** with same settings.
7. Open **Experiment Comparison**, select both — compare fault deltas and working-set overlays.
8. Open **Experiment History**, export summaries as CSV.

---

## Technical Notes

- Worker processes use `multiprocessing` with the Windows `spawn` start method.
- `PageFaultCount` is a cumulative DWORD counter — it counts **all** fault types (soft + hard).  A high count does not imply disk I/O.
- All measurements are real — no synthetic or hardcoded values.
- Database: SQLite with WAL mode (`memory_analyzer.db` in the project directory).
