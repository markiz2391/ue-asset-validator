"""CSV / HTML export of the last run."""
import csv
import html
import os
import time

import unreal

from . import runner


def _out_dir():
    d = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir()), "AssetValidator")
    os.makedirs(d, exist_ok=True)
    return d


def export(fmt="csv"):
    State = runner.State
    fmt = fmt.lower()
    path = os.path.normpath(os.path.join(_out_dir(), time.strftime(f"report_{State.group}_%Y%m%d_%H%M%S.{fmt}")))
    rows = [(i.severity.name, i.check_id, i.asset_path, i.message, "yes" if i.fixable else "") for i in State.issues]
    head = ("Severity", "Check", "Asset", "Message", "Fixable")
    if fmt == "csv":
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(head)
            w.writerows(rows)
    elif fmt == "html":
        colors = {"ERROR": "#d33", "WARNING": "#d90", "INFO": "#888"}
        body = "".join(
            f"<tr><td style='color:{colors[r[0]]}'>{r[0]}</td>" + "".join(f"<td>{html.escape(c)}</td>" for c in r[1:]) + "</tr>"
            for r in rows)
        s = State.stats
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"""<!doctype html><meta charset="utf-8"><title>Asset Validator Report</title>
<style>body{{font:14px system-ui;margin:24px}}table{{border-collapse:collapse;width:100%}}
td,th{{border-bottom:1px solid #ddd;padding:4px 8px;text-align:left}}</style>
<h1>Asset Validator: {html.escape(State.root)}</h1>
<p>{s.get('assets', 0)} assets, {len(rows)} issues, {s.get('seconds', 0)}s</p>
<table><tr>{''.join(f'<th>{h}</th>' for h in head)}</tr>{body}</table>""")
    else:
        raise ValueError(f"Unknown report format {fmt}")
    return path
