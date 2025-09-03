#!/usr/bin/env python3
'''
junit2html_simple.py
----------------
Convert one or more JUnit XML files into a single, pretty HTML report.

Requires:
    pip install junitparser

Usage:
    python junit2html_simple.py -o report.html TEST-*.xml
'''
import argparse
import datetime as dt
import html
import os
from typing import List, Dict, Any

try:
    from junitparser import JUnitXml, TestCase, Failure, Skipped, Error  # type: ignore
except Exception as e:
    MSG = "This script requires 'junitparser'. Install it with: pip install junitparser"
    raise SystemExit(MSG) from e
def _get_test_status(case: TestCase) -> str:
    """Get test case status from junitparser result."""
    if case.result:
        for r in case.result:
            if isinstance(r, Failure):
                return "fail"
            if isinstance(r, Error):
                return "err"
            if isinstance(r, Skipped):
                return "skip"
    return "ok"


def _get_test_message(case: TestCase) -> str:
    """Get test case message from junitparser result."""
    if case.result:
        # show the first message found
        r = case.result[0]
        m = getattr(r, "message", "") or ""
        # Some messages are bytes/None; coerce to str cleanly
        return str(m)
    return ""


def _get_test_detail(case: TestCase) -> str:
    """Get test case detail from junitparser result."""
    if case.result:
        r = case.result[0]
        # Failure/Error text may be on .text
        t = getattr(r, "text", "") or ""
        return str(t)
    return ""


def parse_files(paths: List[str]) -> Dict[str, Any]:
    """Parse JUnit XML files and extract test data."""
    suites_data = []
    case_rows = []

    for p in paths:
        xml = JUnitXml.fromfile(p)
        # xml may be a collection of suites or a single suite; JUnitXml is iterable over suites
        for suite in xml:
            sname = suite.name or os.path.basename(p)
            # tests may be 0/None; fallback to len(cases)
            tests = int(suite.tests or len(list(suite)))
            failures = int(suite.failures or 0)
            errors = int(suite.errors or 0)
            skipped = int(getattr(suite, "skipped", 0) or getattr(suite, "disabled", 0) or 0)
            time = float(suite.time or 0.0)
            suites_data.append({
                "name": sname,
                "tests": tests,
                "failures": failures,
                "errors": errors,
                "skipped": skipped,
                "time": time,
                "file": os.path.basename(p),
            })
            for case in suite:
                if not isinstance(case, TestCase):
                    continue
                case_rows.append({
                    "suite": sname,
                    "classname": case.classname or "",
                    "name": case.name or "",
                    "time": float(case.time or 0.0),
                    "status": _get_test_status(case),
                    "message": _get_test_message(case),
                    "detail": _get_test_detail(case),
                })

    totals = {
        "suites": len(suites_data),
        "tests": sum(s["tests"] for s in suites_data),
        "failures": sum(s["failures"] for s in suites_data),
        "errors": sum(s["errors"] for s in suites_data),
        "skipped": sum(s["skipped"] for s in suites_data),
        "time": sum(s["time"] for s in suites_data),
    }
    totals["passed"] = totals["tests"] - totals["failures"] - totals["errors"] - totals["skipped"]
    return {"suites": suites_data, "cases": case_rows, "totals": totals}
def seconds_fmt(sec: float) -> str:
    """Format seconds as human-readable time string."""
    if sec >= 60:
        m = int(sec // 60)
        s = sec - (m * 60)
        return f"{m}m{s:.2f}s"
    return f"{sec:.2f}s"


def label_of(status: str) -> str:
    """Convert status code to human-readable label."""
    return {"ok":"PASS", "fail":"FAIL", "err":"ERROR", "skip":"SKIP"}.get(status, status)


def _escape_html(x: str) -> str:
    """Escape HTML characters."""
    return html.escape(x, quote=True)


def _build_row_html(c: Dict[str, Any]) -> str:
    """Build HTML for a single test case row."""
    status = c["status"]
    pill_class = {"ok":"ok","fail":"fail","err":"err","skip":"skip"}[status]
    need_details = (status in ("fail", "err") or
                    (status == "skip" and (c["message"] or c["detail"])))
    row_extra_cls = " has-details" if need_details else ""
    details_html = ""
    if need_details:
        details_html = f'''
      <div class="case-details">
        <div class="detail-head">
          <span class="pill {pill_class}">{label_of(status)}</span>
          <span class="detail-msg">{_escape_html(c["message"] or "(no message)")}</span>
        </div>
        <pre>{_escape_html((c["detail"] or "").strip())}</pre>
      </div>
        '''
    return f'''
    <div class="row{row_extra_cls}" tabindex="0" aria-expanded="false" 
         data-suite="{_escape_html(c['suite'])}" data-classname="{_escape_html(c['classname'])}" 
         data-name="{_escape_html(c['name'])}">
      <div class="status {pill_class}">{label_of(status)}</div>
      <div class="nowrap" title="{_escape_html(c['name'])}">{_escape_html(c['name'])}</div>
      <div class="nowrap" title="{_escape_html(c['classname'])}">{_escape_html(c['classname'])}</div>
      <div class="nowrap" title="{_escape_html(c['suite'])}">{_escape_html(c['suite'])}</div>
      <div>{seconds_fmt(float(c['time']))}</div>
      {details_html}
    </div>
    '''

def _build_main_content(data: Dict[str, Any]) -> str:
    """Build main content HTML structure."""
    # Group cases by suite, then by classname
    structure = {}
    for case in data["cases"]:
        suite = case["suite"]
        classname = case["classname"] or "Default"
        # name = case["name"]  # Not used in this function

        if suite not in structure:
            structure[suite] = {}
        if classname not in structure[suite]:
            structure[suite][classname] = []
        structure[suite][classname].append(case)

    main_html = ""

    for suite in sorted(structure.keys()):
        # Calculate suite totals
        suite_cases = [case for cases in structure[suite].values() for case in cases]
        suite_totals = {
            "tests": len(suite_cases),
            "passed": len([c for c in suite_cases if c["status"] == "ok"]),
            "failures": len([c for c in suite_cases if c["status"] == "fail"]),
            "errors": len([c for c in suite_cases if c["status"] == "err"]),
            "skipped": len([c for c in suite_cases if c["status"] == "skip"]),
            "time": sum(c["time"] for c in suite_cases)
        }

        main_html += f'''
    <div class="suite-section" data-suite="{_escape_html(suite)}">
      <div class="suite-header" data-type="suite" data-suite="{_escape_html(suite)}">
        <div class="suite-title">
          <span class="collapse-icon">▼</span>
          <span class="item-icon">📁</span>
          <span class="item-text">{_escape_html(suite)}</span>
        </div>
        <div class="suite-summary">
          <span class="pill">Tests: {suite_totals["tests"]}</span>
          <span class="pill ok">PASS: {suite_totals["passed"]}</span>
          <span class="pill fail">FAIL: {suite_totals["failures"]}</span>
          <span class="pill err">ERROR: {suite_totals["errors"]}</span>
          <span class="pill skip">SKIP: {suite_totals["skipped"]}</span>
          <span class="pill">Time: {seconds_fmt(suite_totals["time"])}</span>
        </div>
      </div>
      <div class="suite-content">
'''

        for classname in sorted(structure[suite].keys()):
            class_cases = structure[suite][classname]
            class_totals = {
                "tests": len(class_cases),
                "passed": len([c for c in class_cases if c["status"] == "ok"]),
                "failures": len([c for c in class_cases if c["status"] == "fail"]),
                "errors": len([c for c in class_cases if c["status"] == "err"]),
                "skipped": len([c for c in class_cases if c["status"] == "skip"]),
                "time": sum(c["time"] for c in class_cases)
            }

            main_html += f'''
        <div class="class-section" data-suite="{_escape_html(suite)}" data-classname="{_escape_html(classname)}">
          <div class="class-header" data-type="class" data-suite="{_escape_html(suite)}" data-classname="{_escape_html(classname)}">
            <div class="class-title">
              <span class="collapse-icon">▼</span>
              <span class="item-icon">📦</span>
              <span class="item-text">{_escape_html(classname)}</span>
            </div>
            <div class="class-summary">
              <span class="pill">Tests: {class_totals["tests"]}</span>
              <span class="pill ok">PASS: {class_totals["passed"]}</span>
              <span class="pill fail">FAIL: {class_totals["failures"]}</span>
              <span class="pill err">ERROR: {class_totals["errors"]}</span>
              <span class="pill skip">SKIP: {class_totals["skipped"]}</span>
              <span class="pill">Time: {seconds_fmt(class_totals["time"])}</span>
            </div>
          </div>
          <div class="class-content">
            <div class="class-grid">
              <div>Status</div>
              <div>TestName</div>
              <div>Category / Suite</div>
              <div>SuiteName</div>
              <div>Elapse Time</div>
            </div>
'''

            for case in sorted(class_cases, key=lambda x: x["name"]):
                main_html += _build_row_html(case)

            main_html += '''
          </div>
        </div>
'''

        main_html += '''
      </div>
    </div>
'''

    return main_html

def _build_sidebar(data: Dict[str, Any], title: str) -> str:
    """Build sidebar HTML structure."""
    # Group cases by suite, then by classname
    structure = {}
    for case in data["cases"]:
        suite = case["suite"]
        classname = case["classname"] or "Default"
        name = case["name"]

        if suite not in structure:
            structure[suite] = {}
        if classname not in structure[suite]:
            structure[suite][classname] = []
        structure[suite][classname].append(name)

    sidebar_html = '<div class="sidebar">\n'
    sidebar_html += '<div class="sidebar-header">\n'
    sidebar_html += '<div class="sidebar-title">Test Structure</div>\n'
    sidebar_html += '<div class="sidebar-search">\n'
    sidebar_html += f'<input type="search" placeholder="Search {_escape_html(title)}..." />\n'
    sidebar_html += '</div>\n'
    sidebar_html += '<div class="sidebar-content">\n'

    for suite in sorted(structure.keys()):
        sidebar_html += (f'<div class="sidebar-item suite-item" '
                        f'data-suite="{_escape_html(suite)}">\n')
        sidebar_html += (f'  <div class="sidebar-label" data-type="suite" '
                        f'data-suite="{_escape_html(suite)}">\n')
        sidebar_html +=  '    <span class="collapse-icon">▼</span>\n'
        sidebar_html +=  '    <span class="item-icon">📁</span>\n'
        sidebar_html += f'    <span class="item-text">{_escape_html(suite)}</span>\n'
        sidebar_html +=  '  </div>\n'
        sidebar_html +=  '  <div class="sidebar-children suite-children">\n'

        for classname in sorted(structure[suite].keys()):
            sidebar_html += (f'    <div class="sidebar-item class-item" '
                            f'data-suite="{_escape_html(suite)}" '
                            f'data-classname="{_escape_html(classname)}">\n')
            sidebar_html += (f'      <div class="sidebar-label" data-type="class" '
                            f'data-suite="{_escape_html(suite)}" '
                            f'data-classname="{_escape_html(classname)}">\n')
            sidebar_html +=  '        <span class="collapse-icon">▼</span>\n'
            sidebar_html +=  '        <span class="item-icon">📦</span>\n'
            sidebar_html += f'        <span class="item-text">{_escape_html(classname)}</span>\n'
            sidebar_html +=  '      </div>\n'
            sidebar_html +=  '      <div class="sidebar-children class-children">\n'

            for name in sorted(structure[suite][classname]):
                sidebar_html += (f'        <div class="sidebar-item case-item" '
                                f'data-suite="{_escape_html(suite)}" '
                                f'data-classname="{_escape_html(classname)}" '
                                f'data-name="{_escape_html(name)}">\n')
                sidebar_html += (f'          <div class="sidebar-label" data-type="case" '
                                f'data-suite="{_escape_html(suite)}" '
                                f'data-classname="{_escape_html(classname)}" '
                                f'data-name="{_escape_html(name)}">\n')
                sidebar_html += '            <span class="item-icon">🧪</span>\n'
                sidebar_html += f'            <span class="item-text">{_escape_html(name)}</span>\n'
                sidebar_html +=  '          </div>\n'
                sidebar_html +=  '        </div>\n'

            sidebar_html += '      </div>\n'
            sidebar_html += '    </div>\n'

        sidebar_html += '  </div>\n'
        sidebar_html += '</div>\n'

    sidebar_html += '</div>\n'
    sidebar_html += '</div>\n'
    return sidebar_html

def render_html(data: Dict[str, Any], title: str = "Report") -> str:
    """Render test data as HTML report."""
    t = data["totals"]
    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    main_content_html = _build_main_content(data)
    sidebar_html = _build_sidebar(data, title)

    html_out = f'''<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>{_escape_html(title)}</title>
<style>
  :root {{ --ok:#2e7d32; --skip:#8d6e63; --fail:#c62828; --err:#6a1b9a; --fg:#1f2937; --muted:#6b7280; }}
  body {{ font-family: ui-sans-serif, system-ui, -apple-system, "Noto Sans TC", Arial, "Segoe UI"; color: var(--fg); margin: 0; }}

  /* Layout */
  .container {{
    display: flex !important;
    min-height: 100vh;
    flex-direction: row !important;
    width: 100%;
    background: #f0f0f0;
  }}
  .sidebar {{
    width: 300px !important;
    min-width: 300px !important;
    background: #f8fafc;
    border-right: 2px solid #e2e8f0;
    overflow-y: auto;
    flex-shrink: 0 !important;
    flex-grow: 0 !important;
  }}
  .main-content {{
    flex: 1 !important;
    flex-grow: 1 !important;
    padding: 24px;
    overflow-x: auto;
    min-width: 0;
    background: #ffffff;
  }}

  /* Sidebar Styles */
  .sidebar-header {{
    padding: 16px;
    border-bottom: 1px solid #e2e8f0;
    background: #f8fafc;
  }}
  .sidebar-title {{
    font-weight: 600;
    font-size: 16px;
    color: #334155;
    margin-bottom: 12px;
  }}
  .sidebar-search {{
    position: relative;
  }}
  .sidebar-search input {{
    width: 100%;
    padding: 10px 12px;
    border: 1px solid #d1d5db;
    border-radius: 8px;
    background: #fff;
    font-size: 13px;
    color: #374151;
    transition: all 0.2s ease;
    box-sizing: border-box;
    font-family: inherit;
  }}
  .sidebar-search input:focus {{
    border-color: #2563eb;
    box-shadow: 0 0 0 3px rgba(37,99,235,0.15);
    outline: none;
    background: #fafbfc;
  }}
  .sidebar-search input::placeholder {{
    color: #9ca3af;
    font-style: italic;
  }}
  .sidebar-content {{ padding: 8px; }}
  .sidebar-item {{ margin: 2px 0; }}
  .sidebar-label {{
    display: flex;
    align-items: center;
    padding: 8px 12px;
    cursor: pointer;
    border-radius: 6px;
    font-size: 13px;
    transition: all 0.2s ease;
    user-select: none;
    border: 1px solid transparent;
  }}
  .sidebar-label:hover {{
    background: #f1f5f9;
    border-color: #e2e8f0;
  }}
  .sidebar-label:active {{
    background: #e2e8f0;
    transform: translateY(1px);
  }}

  .collapse-icon {{
    width: 16px;
    height: 16px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 10px;
    color: #64748b;
    margin-right: 8px;
    transition: transform 0.2s ease;
    flex-shrink: 0;
  }}
  .sidebar-item.collapsed .collapse-icon {{
    transform: rotate(-90deg);
  }}
  .case-item .collapse-icon {{
    visibility: hidden;
  }}

  .item-icon {{
    margin-right: 8px;
    font-size: 14px;
    flex-shrink: 0;
  }}
  .item-text {{
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    font-weight: 500;
  }}

  .sidebar-children {{
    margin-left: 20px;
    overflow: hidden;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    border-left: 2px solid #e2e8f0;
    margin-top: 4px;
    padding-left: 12px;
  }}
  .sidebar-item.collapsed .sidebar-children {{
    max-height: 0;
    opacity: 0;
    margin-top: 0;
    padding-top: 0;
    padding-bottom: 0;
  }}

  .suite-item .sidebar-label {{
    font-weight: 600;
    color: #1e40af;
    background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%);
    border-color: #bfdbfe;
  }}
  .suite-item .sidebar-label:hover {{
    background: linear-gradient(135deg, #dbeafe 0%, #bfdbfe 100%);
    border-color: #93c5fd;
  }}

  .class-item .sidebar-label {{
    font-weight: 600;
    color: #059669;
    background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%);
    border-color: #bbf7d0;
  }}
  .class-item .sidebar-label:hover {{
    background: linear-gradient(135deg, #dcfce7 0%, #bbf7d0 100%);
    border-color: #86efac;
  }}

  .case-item .sidebar-label {{
    color: #374151;
    padding-left: 28px;
    background: #fff;
    border-color: #f1f5f9;
  }}
  .case-item .sidebar-label:hover {{
    background: #f8fafc;
    border-color: #e2e8f0;
  }}

  /* Main Content Styles */
  h1 {{ font-size: 20px; margin: 0 0 12px; }}
  .pill {{ padding:4px 10px; border-radius:999px; font-size:12px; background:#eef2ff; }}
  .pill.ok {{ background:#e8f5e9; color:var(--ok); }}
  .pill.fail {{ background:#ffebee; color:var(--fail); }}
  .pill.err {{ background:#f3e5f5; color:var(--err); }}
  .pill.skip {{ background:#efebe9; color:var(--skip); }}
  .muted {{ color: var(--muted); font-size:12px; }}

  /* Suite and Class Section Styles */
  .suite-section {{
    margin-bottom: 24px;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    overflow: hidden;
    background: #ffffff;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
  }}

  .suite-header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 16px 20px;
    background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%);
    border-bottom: 1px solid #bfdbfe;
    cursor: pointer;
    transition: all 0.2s ease;
  }}
  .suite-header:hover {{
    background: linear-gradient(135deg, #dbeafe 0%, #bfdbfe 100%);
  }}

  .suite-title {{
    display: flex;
    align-items: center;
    font-weight: 600;
    font-size: 16px;
    color: #1e40af;
  }}

  .suite-summary {{
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
  }}

  .suite-content {{
    overflow: hidden;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  }}
  .suite-section.collapsed .suite-content {{
    max-height: 0;
    opacity: 0;
    padding-top: 0;
    padding-bottom: 0;
  }}

  .class-section {{
    margin: 16px;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    overflow: hidden;
    background: #f8fafc;
  }}

  .class-header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px 16px;
    background: linear-gradient(135deg, #f0fdf4 0%, #dcfce7 100%);
    border-bottom: 1px solid #bbf7d0;
    cursor: pointer;
    transition: all 0.2s ease;
  }}
  .class-header:hover {{
    background: linear-gradient(135deg, #dcfce7 0%, #bbf7d0 100%);
  }}

  .class-title {{
    display: flex;
    align-items: center;
    font-weight: 600;
    font-size: 14px;
    color: #059669;
  }}

  .class-summary {{
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
  }}

  .class-content {{
    overflow: hidden;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  }}
  .class-section.collapsed .class-content {{
    max-height: 0;
    opacity: 0;
    padding-top: 0;
    padding-bottom: 0;
  }}

  .suite-grid, .class-grid {{
    display: grid;
    grid-template-columns: 80px 2fr 1fr 1fr 100px;
    gap: 8px;
    margin: 12px 20px 4px;
    font-weight: 600;
    font-size: 13px;
    color: #374151;
    padding: 8px 12px;
    background: #f9fafb;
    border-radius: 6px;
  }}

  .row {{
    display: grid;
    grid-template-columns: 80px 2fr 1fr 1fr 100px;
    gap: 8px;
    padding: 10px 12px;
    border-bottom: 1px solid #e5e7eb;
    align-items: start;
    margin: 0 20px;
    background: #ffffff;
    border-radius: 4px;
    margin-bottom: 4px;
  }}
  .row:hover {{ background:#f9fafb; }}
  .row.highlighted {{ background: #fef3c7; border-left: 3px solid #f59e0b; }}
  .status.ok {{ color:var(--ok); font-weight:600; }}
  .status.fail {{ color:var(--fail); font-weight:600; }}
  .status.err {{ color:var(--err); font-weight:600; }}
  .status.skip {{ color:var(--skip); font-weight:600; }}
  details {{ grid-column: 1 / -1; background:#fff; border:1px solid #e5e7eb; border-radius:8px; padding:8px 10px; }}
  details pre {{ overflow:auto; white-space:pre-wrap; word-break:break-word; margin:10px 0 0; }}
  .summary {{ display:flex; gap:8px; align-items:center; flex-wrap:wrap; }}
  .totals {{ display:flex; gap:8px; flex-wrap:wrap; }}
  .small {{ font-size:12px; }}
  .nowrap {{ white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
  .controls {{ display:flex; gap:8px; flex-wrap:wrap; align-items:center; margin: 8px 0 16px; }}

  /* Search and Filter Styles */
  input[type="search"] {{
    padding: 6px 10px;
    border: 1px solid #d1d5db;
    border-radius: 6px;
    background-color: #fff;
    font-family: inherit;
    font-size: 14px;
    color: #374151;
    line-height: 1.5;
    transition: border-color 0.2s, box-shadow 0.2s;
  }}

  input[type="search"]:focus {{
    border-color: #2563eb;
    box-shadow: 0 0 0 2px rgba(37,99,235,0.2);
    outline: none;
  }}

  input[type="search"]:hover {{
    border-color: #9ca3af;
  }}

  select {{
    padding: 6px 28px 6px 10px;
    border: 1px solid #d1d5db;
    border-radius: 6px;
    background-color: #fff;
    font-family: inherit;
    font-size: 14px;
    color: #374151;
    line-height: 1.5;
    appearance: none;
    -webkit-appearance: none;
    -moz-appearance: none;
    background-image: url("data:image/svg+xml;base64,PHN2ZyBmaWxsPSJub25lIiBzdHJva2U9IiM2YjcyODAiIHN0cm9rZS13aWR0aD0iMiIgdmlld0JveD0iMCAwIDI0IDI0IiB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciPjxwYXRoIGQ9Ik02IDlsNiA2IDYtNiIvPjwvc3ZnPg==");
    background-repeat: no-repeat;
    background-position: right 8px center;
    background-size: 16px;
    transition: border-color 0.2s, box-shadow 0.2s;
  }}

  select:focus {{
    border-color: #2563eb;
    box-shadow: 0 0 0 2px rgba(37,99,235,0.2);
    outline: none;
  }}

  select:hover {{
    border-color: #9ca3af;
  }}

  select option {{
    padding: 6px 10px;
    font-size: 14px;
  }}

  select option:hover {{
    background-color: #f3f4f6;
  }}

  /* Row Details */
  .row.has-details {{ cursor: pointer; }}
  .row.has-details:focus {{ outline: 2px solid #c7d2fe; outline-offset: 2px; }}
  .case-details {{ display:none; grid-column: 1 / -1; background:#fff; border:1px solid #e5e7eb; border-radius:8px; padding:10px 12px; margin-top:8px; }}
  .row.expanded .case-details {{ display:block; }}
  .case-details pre {{ overflow:auto; white-space:pre-wrap; word-break:break-word; margin:10px 0 0; }}
  .detail-head {{ display:flex; gap:8px; align-items:center; flex-wrap:wrap; font-weight:600; }}
  .detail-msg {{ color:#374151; }}

  /* Responsive */
  @media (max-width: 768px) {{
    .container {{ flex-direction: column; }}
    .sidebar {{ width: 100%; max-height: 200px; }}
    .main-content {{ padding: 16px; }}
    .suite-header, .class-header {{
      flex-direction: column;
      align-items: flex-start;
      gap: 8px;
    }}
    .suite-summary, .class-summary {{
      justify-content: flex-start;
    }}
  }}
</style>
</head>
<body>
  <div class="container">
    {sidebar_html}

  </div>
  <div class="main-content">
    <h1>{_escape_html(title)}</h1>
    <div class="muted small">Generate Time : {_escape_html(now)}</div>

    <div class="totals" style="margin-top:10px;">
      <span class="pill">Suite : {t["suites"]}</span>
      <span class="pill">Test : {t["tests"]}</span>
      <span class="pill ok">PASS : {t["passed"]}</span>
      <span class="pill fail">FAIL : {t["failures"]}</span>
      <span class="pill err">ERROR : {t["errors"]}</span>
      <span class="pill skip">SKIP : {t["skipped"]}</span>
      <span class="pill">Elapse Time : {seconds_fmt(float(t["time"]))}</span>
    </div>
    <div class="controls">
      <input id="search" type="search" placeholder="Search : Category/Name/Message..." />
      <select id="status-filter" title="Status Filter">
        <option value="">ALL</option>
        <option value="ok">PASS</option>
        <option value="fail">FAIL</option>
        <option value="err">ERROR</option>
        <option value="skip">SKIP</option>
      </select>
      <select id="sort" title="Sort">
        <option value="status">Status</option>
        <option value="time">Elapse Time(Long -> Short)</option>
        <option value="name">TestName</option>
      </select>
    </div>

    <div id="content">
      {main_content_html}
    </div>
  </div>

<script>
(function(){{
  const searchEl = document.getElementById('search');
  const filterEl = document.getElementById('status-filter');
  const sortEl = document.getElementById('sort');
  const contentEl = document.getElementById('content');

  // collect all rows into an in-memory array for filtering/sorting
  const rows = [...contentEl.querySelectorAll('.row')].map(r => {{
    const cells = r.querySelectorAll(':scope > div');
    const container = r.closest('.class-content');
    const statusKey = labelToKey(cells[0].textContent.trim());
    return {{
      el: r,
      container: container,
      statusKey: statusKey,
      status: cells[0].textContent.trim(),
      name: cells[1].textContent.trim().toLowerCase(),
      classname: cells[2].textContent.trim().toLowerCase(),
      suite: cells[3].textContent.trim().toLowerCase(),
      time: parseFloat(cells[4].textContent.trim().replace('s','')) || 0
    }};
  }});

  function labelToKey(s){{ return s==='PASS'?'ok': s==='FAIL'?'fail' : s==='ERROR'?'err' : s==='SKIP'?'skip':''; }}

  function apply(){{
    const q = (searchEl.value || '').trim().toLowerCase();
    const statusFilter = filterEl.value;
    const sortBy = sortEl.value;

    // switch
    rows.forEach(r => {{
      const inSearch = !q || (r.name.includes(q) || r.classname.includes(q) || r.suite.includes(q) || (r.el.textContent || '').toLowerCase().includes(q));
      const inStatus = !statusFilter || r.statusKey === statusFilter;
      r.el.style.display = (inSearch && inStatus) ? '' : 'none';
    }});

    // aquire
    const containers = new Set(rows.map(r => r.container));

    // sort in vis
    containers.forEach(container => {{
      if (!container) return;

      // gain rows
      const visibleRows = rows.filter(r => r.container === container && r.el.style.display !== 'none');

      // sort
      visibleRows.sort((a, b) => {{
        if (sortBy === 'time') return (b.time || 0) - (a.time || 0);
        if (sortBy === 'name') return (a.name || '').localeCompare(b.name || '');
        // status sort：ERROR(0) < FAIL(1) < SKIP(2) < PASS(3)
        const statusOrder = {{ 'err': 0, 'fail': 1, 'skip': 2, 'ok': 3 }};
        return (statusOrder[a.statusKey] - statusOrder[b.statusKey]) || (b.time - a.time);
      }});

      // reduce reflow
      const fragment = document.createDocumentFragment();
      visibleRows.forEach(row => fragment.appendChild(row.el));
      container.appendChild(fragment);
    }});

    // collapse
    document.querySelectorAll('.class-section').forEach(classSection => {{
      const hasVisibleRows = classSection.querySelectorAll('.row[style*="display: none"]').length <
                            classSection.querySelectorAll('.row').length;

      if (hasVisibleRows) {{
        classSection.style.display = '';
        classSection.classList.remove('collapsed');
      }} else {{
        classSection.style.display = 'none';
      }}
    }});

    // suite-section vis
    document.querySelectorAll('.suite-section').forEach(suiteSection => {{
      const hasVisibleClassSections = suiteSection.querySelectorAll('.class-section[style*="display: none"]').length <
                                     suiteSection.querySelectorAll('.class-section').length;

      if (hasVisibleClassSections) {{
        suiteSection.style.display = '';
        suiteSection.classList.remove('collapsed');
      }} else {{
        suiteSection.style.display = 'none';
      }}
    }});
  }}

  function bindRowToggle() {{
    const rowEls = contentEl.querySelectorAll('.row.has-details');
    rowEls.forEach(r => {{
      const toggle = () => {{
        const expanded = r.classList.toggle('expanded');
        r.setAttribute('aria-expanded', expanded ? 'true' : 'false');
      }};
      r.addEventListener('click', (e) => {{
        if (e.target.closest('.case-details')) return;
        toggle();
      }});
      r.addEventListener('keydown', (e) => {{
        if (e.key === 'Enter' || e.key === ' ') {{
          e.preventDefault();
          toggle();
        }}
      }});
    }});
  }}

  function bindMainContentCollapse() {{
    // Handle suite collapse/expand
    const suiteHeaders = document.querySelectorAll('.suite-header');
    suiteHeaders.forEach(header => {{
      header.addEventListener('click', (e) => {{
        e.stopPropagation();
        const suiteSection = header.closest('.suite-section');
        suiteSection.classList.toggle('collapsed');
      }});
    }});

    // Handle class collapse/expand
    const classHeaders = document.querySelectorAll('.class-header');
    classHeaders.forEach(header => {{
      header.addEventListener('click', (e) => {{
        e.stopPropagation();
        const classSection = header.closest('.class-section');
        classSection.classList.toggle('collapsed');
      }});
    }});
  }}

  function bindSidebarNavigation() {{
    const sidebarItems = document.querySelectorAll('.sidebar-item');

    sidebarItems.forEach(item => {{
      item.addEventListener('click', (e) => {{
        e.stopPropagation();

        // Handle collapse/expand for suite and class items
        const label = e.target.closest('.sidebar-label');
        if (label && (label.getAttribute('data-type') === 'suite' || label.getAttribute('data-type') === 'class')) {{
          const parentItem = label.closest('.sidebar-item');
          parentItem.classList.toggle('collapsed');
          return;
        }}

        // Handle navigation for all items
        // Remove previous highlights
        document.querySelectorAll('.row.highlighted').forEach(row => {{
          row.classList.remove('highlighted');
        }});

        const suite = item.getAttribute('data-suite');
        const classname = item.getAttribute('data-classname');
        const name = item.getAttribute('data-name');

        // Find matching rows
        document.querySelectorAll('.row').forEach(row => {{
          const rowSuite = row.getAttribute('data-suite');
          const rowClassname = row.getAttribute('data-classname');
          const rowName = row.getAttribute('data-name');

          let match = false;
          if (name && classname && suite) {{
            // Test case level
            match = rowSuite === suite && rowClassname === classname && rowName === name;
          }} else if (classname && suite) {{
            // Class level
            match = rowSuite === suite && rowClassname === classname;
          }} else if (suite) {{
            // Suite level
            match = rowSuite === suite;
          }}

          if (match) {{
            row.classList.add('highlighted');
            row.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
          }}
        }});
      }});
    }});
  }}

  function bindSidebarSearch() {{
    const searchInput = document.querySelector('.sidebar-search input');
    const sidebarItems = document.querySelectorAll('.sidebar-item');
    const suiteSections = document.querySelectorAll('.suite-section');
    const classSections = document.querySelectorAll('.class-section');
    const rows = document.querySelectorAll('.row');

    searchInput.addEventListener('input', (e) => {{
      const query = e.target.value.toLowerCase().trim();

      // Reset all sections to visible first
      suiteSections.forEach(section => {{
        section.style.display = '';
        section.classList.remove('collapsed');
      }});

      classSections.forEach(section => {{
        section.style.display = '';
        section.classList.remove('collapsed');
      }});

      // Reset sidebar items
      sidebarItems.forEach(item => {{
        item.style.display = '';
        item.classList.remove('collapsed');
      }});

      // Reset all rows to visible
      rows.forEach(row => {{
        row.style.display = '';
      }});

      if (query === '') {{
        // If no search query, show everything
        return;
      }}

      // Track which suites, classes, and cases have matches
      const matchingSuites = new Set();
      const matchingClasses = new Set();
      const matchingCases = new Set();

      // Check sidebar items for matches
      sidebarItems.forEach(item => {{
        const label = item.querySelector('.sidebar-label');
        const text = label.textContent.toLowerCase();
        const hasMatch = text.includes(query);

        if (hasMatch) {{
          const suite = item.getAttribute('data-suite');
          const classname = item.getAttribute('data-classname');
          const name = item.getAttribute('data-name');

          if (suite) {{
            matchingSuites.add(suite);
            if (classname) {{
              matchingClasses.add(suite + ':' + classname);
              if (name) {{
                matchingCases.add(suite + ':' + classname + ':' + name);
              }}
            }}
          }}
        }}
      }});

      // Check main content rows for matches
      rows.forEach(row => {{
        const suite = row.getAttribute('data-suite');
        const classname = row.getAttribute('data-classname');
        const name = row.getAttribute('data-name');
        const rowText = row.textContent.toLowerCase();
        const hasMatch = rowText.includes(query);

        if (hasMatch && suite && classname) {{
          matchingSuites.add(suite);
          matchingClasses.add(suite + ':' + classname);
          if (name) {{
            matchingCases.add(suite + ':' + classname + ':' + name);
          }}
        }}
      }});

      // Show/hide suite sections based on matches
      suiteSections.forEach(section => {{
        const suiteName = section.getAttribute('data-suite');
        const hasMatch = matchingSuites.has(suiteName);

        if (hasMatch) {{
          section.style.display = '';
          section.classList.remove('collapsed');
        }} else {{
          section.style.display = 'none';
        }}
      }});

      // Show/hide class sections based on matches
      classSections.forEach(section => {{
        const suiteName = section.getAttribute('data-suite');
        const className = section.getAttribute('data-classname');
        const classKey = suiteName + ':' + className;
        const hasMatch = matchingClasses.has(classKey);

        if (hasMatch) {{
          section.style.display = '';
          section.classList.remove('collapsed');
        }} else {{
          section.style.display = 'none';
        }}
      }});

      // Show/hide rows based on matches
      rows.forEach(row => {{
        const suite = row.getAttribute('data-suite');
        const classname = row.getAttribute('data-classname');
        const name = row.getAttribute('data-name');

        let shouldShow = false;

        if (suite && classname && name) {{
          // Case level: only show if case matches
          const caseKey = suite + ':' + classname + ':' + name;
          shouldShow = matchingCases.has(caseKey);
        }} else if (suite && classname) {{
          // Class level: show all cases in this class
          const classKey = suite + ':' + classname;
          shouldShow = matchingClasses.has(classKey);
        }} else if (suite) {{
          // Suite level: show all cases in this suite
          shouldShow = matchingSuites.has(suite);
        }}

        // Hide the row if it shouldn't be shown
        if (!shouldShow) {{
          row.style.display = 'none';
        }} else {{
          row.style.display = '';
          // Ensure the row is visible within its proper structure
          const parentClassSection = row.closest('.class-section');
          if (parentClassSection) {{
            parentClassSection.style.display = '';
            parentClassSection.classList.remove('collapsed');
          }}
          const parentSuiteSection = row.closest('.suite-section');
          if (parentSuiteSection) {{
            parentSuiteSection.style.display = '';
            parentSuiteSection.classList.remove('collapsed');
          }}
        }}
      }});

      // Update sidebar visibility
      sidebarItems.forEach(item => {{
        const suite = item.getAttribute('data-suite');
        const classname = item.getAttribute('data-classname');
        const name = item.getAttribute('data-name');

        let shouldShow = false;

        if (item.classList.contains('suite-item')) {{
          shouldShow = matchingSuites.has(suite);
        }} else if (item.classList.contains('class-item')) {{
          const classKey = suite + ':' + classname;
          shouldShow = matchingClasses.has(classKey);
        }} else if (item.classList.contains('case-item')) {{
          const caseKey = suite + ':' + classname + ':' + name;
          shouldShow = matchingCases.has(caseKey);
        }}

        if (shouldShow) {{
          item.style.display = '';
          // Show parent items
          let parent = item.parentElement.closest('.sidebar-item');
          while (parent) {{
            parent.style.display = '';
            parent.classList.remove('collapsed');
            parent = parent.parentElement.closest('.sidebar-item');
          }}
        }} else {{
          item.style.display = 'none';
        }}
      }});
    }});
  }}

  // Initialize
  bindRowToggle();
  bindMainContentCollapse();
  bindSidebarNavigation();
  bindSidebarSearch();

  searchEl.addEventListener('input', apply);
  document.querySelector('.sidebar-search input').addEventListener('input', apply);
  filterEl.addEventListener('change', apply);
  sortEl.addEventListener('change', apply);
}})();
</script>

</body>
</html>
'''
    return html_out
def main():
    """Main entry point for the script."""
    ap = argparse.ArgumentParser(description="Convert JUnit XML to a single HTML report")
    ap.add_argument("inputs", nargs="+", help="JUnit XML files (e.g., TEST-*.xml)")
    ap.add_argument("-o", "--output", default="junit-report.html", help="Output HTML path")
    ap.add_argument("--title", default="JUnit Report", help="Report title")
    args = ap.parse_args()

    data = parse_files(args.inputs)
    html_str = render_html(data, title=args.title)

    with open(args.output, "w", encoding="utf-8") as f:
        f.write(html_str)

    print(f"[V] Wrote {args.output}")
    totals = data['totals']
    passed = totals['tests'] - totals['failures'] - totals['errors'] - totals['skipped']
    print(f"Suites: {totals['suites']}, Tests: {totals['tests']}, "
          f"Passed: {passed}, Failures: {totals['failures']}, "
          f"Errors: {totals['errors']}, Skipped: {totals['skipped']}")


if __name__ == "__main__":
    main()
