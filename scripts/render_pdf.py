#!/usr/bin/env python3
"""
Generate a clean, publication-grade HTML and PDF of the GCP PCA cheatsheet.
"""

import os
import re
import subprocess
from pathlib import Path
from markdown_it import MarkdownIt

WORKSPACE = Path(__file__).resolve().parent.parent
MD_FILE = WORKSPACE / "GCP Professional Cloud Architect (PCA).md"
HTML_FILE = WORKSPACE / "GCP Professional Cloud Architect (PCA).html"
PDF_FILE = WORKSPACE / "GCP Professional Cloud Architect (PCA).pdf"

def parse_markdown(text: str) -> str:
    md = MarkdownIt().enable('table').enable('strikethrough')
    
    # Process callout notes: > [!NOTE] ...
    # Convert alert syntax before markdown parsing
    alert_pattern = re.compile(r'>\s*\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]\s*\n((?:>\s*.*\n?)+)', re.MULTILINE)
    
    def alert_sub(m):
        alert_type = m.group(1)
        raw_lines = m.group(2).splitlines()
        cleaned_lines = [re.sub(r'^>\s?', '', l) for l in raw_lines]
        body_text = "\n".join(cleaned_lines)
        return f':::ALERT-{alert_type}:::\n{body_text}\n:::ENDALERT:::\n'

    processed_text = alert_pattern.sub(alert_sub, text)
    
    # Render with MarkdownIt
    raw_html = md.render(processed_text)
    
    # Replace alert placeholders with nice HTML divs
    def restore_alert(m):
        alert_type = m.group(1).lower()
        content = m.group(2).strip()
        inner_html = md.render(content)
        title = alert_type.upper()
        return f'''<div class="callout callout-{alert_type}">
    <div class="callout-badge">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <circle cx="12" cy="12" r="10"></circle>
            <line x1="12" y1="16" x2="12" y2="12"></line>
            <line x1="12" y1="8" x2="12.01" y2="8"></line>
        </svg>
        <span>{title}</span>
    </div>
    <div class="callout-body">{inner_html}</div>
</div>'''

    raw_html = re.sub(r'<p>:::ALERT-(\w+):::</p>\s*(.*?)\s*<p>:::ENDALERT:::</p>', restore_alert, raw_html, flags=re.DOTALL)
    
    # Enhance Decision rule block
    def enhance_decision_rule(m):
        content = m.group(1).strip()
        if "→" in content:
            parts = content.split(".", 1)
            chain = parts[0]
            explanation = parts[1].strip() if len(parts) > 1 else ""
            
            steps = [s.strip() for s in chain.split("→")]
            steps_html = "".join([
                f'<span class="step-badge">{step}</span>' + ('<span class="step-arrow">➔</span>' if i < len(steps)-1 else '')
                for i, step in enumerate(steps)
            ])
            return f'''<div class="decision-card">
    <div class="decision-card-header">
        <span class="decision-icon">🎯</span>
        <span class="decision-title">Compute Decision Hierarchy</span>
    </div>
    <div class="decision-flow">{steps_html}</div>
    {f'<div class="decision-note">{explanation}.</div>' if explanation else ''}
</div>'''
        return f'<div class="decision-card">{content}</div>'

    raw_html = re.sub(r'<p><strong>Decision rule:</strong>\s*(.*?)</p>', enhance_decision_rule, raw_html, flags=re.DOTALL)
    
    # Enhance table formatting: add badges to AWS equivalent column
    def enhance_table_cells(m):
        tr_content = m.group(1)
        if '<td>' in tr_content:
            tds = re.findall(r'<td>(.*?)</td>', tr_content, flags=re.DOTALL)
            if len(tds) == 3:
                gcp = tds[0]
                aws = tds[1]
                choose = tds[2]
                
                # Badge for AWS
                if aws.strip() and aws.strip() != '-':
                    aws_badge = f'<span class="aws-pill">{aws}</span>'
                else:
                    aws_badge = aws
                
                # Highlight exam keywords in Choose column
                highlighted_choose = re.sub(
                    r'(Exam keyword:|Keyword:|Default answer for)',
                    r'<span class="exam-kw-tag">\1</span>',
                    choose
                )
                
                return f'<tr><td class="col-gcp">{gcp}</td><td class="col-aws">{aws_badge}</td><td class="col-choose">{highlighted_choose}</td></tr>'
        return f'<tr>{tr_content}</tr>'

    raw_html = re.sub(r'<tr>(.*?)</tr>', enhance_table_cells, raw_html, flags=re.DOTALL)

    return raw_html

def build_full_html(body_content: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>GCP Professional Cloud Architect (PCA) — Service Cheatsheet</title>
<style>
    @page {{
        size: letter portrait;
        margin: 14mm 12mm 16mm 12mm;
        @bottom-right {{
            content: "Page " counter(page) " of " counter(pages);
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            font-size: 8pt;
            color: #64748b;
        }}
        @bottom-left {{
            content: "Google Cloud PCA Quick Reference • AWS Crosswalk";
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            font-size: 8pt;
            color: #64748b;
        }}
    }}

    * {{
        box-sizing: border-box;
        margin: 0;
        padding: 0;
    }}

    body {{
        font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
        color: #1e293b;
        background-color: #ffffff;
        font-size: 9pt;
        line-height: 1.45;
        -webkit-print-color-adjust: exact;
        print-color-adjust: exact;
    }}

    /* Top Accent Bar */
    .gcp-top-bar {{
        display: flex;
        height: 4px;
        width: 100%;
        margin-bottom: 14px;
    }}
    .bar-blue   {{ flex: 1; background-color: #4285f4; }}
    .bar-red    {{ flex: 1; background-color: #ea4335; }}
    .bar-yellow {{ flex: 1; background-color: #fbbc04; }}
    .bar-green  {{ flex: 1; background-color: #34a853; }}

    /* Header Container */
    .header-container {{
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        border-bottom: 1.5px solid #e2e8f0;
        padding-bottom: 10px;
        margin-bottom: 12px;
    }}

    .header-title-area h1 {{
        font-size: 16pt;
        font-weight: 700;
        color: #0f172a;
        letter-spacing: -0.02em;
        margin-bottom: 4px;
    }}

    .header-subtitle {{
        font-size: 9pt;
        color: #475569;
        font-weight: 500;
    }}

    .header-badges {{
        display: flex;
        gap: 6px;
        align-items: center;
    }}

    .header-badge {{
        font-size: 7.5pt;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        padding: 3px 8px;
        border-radius: 4px;
        background-color: #eff6ff;
        color: #1d4ed8;
        border: 1px solid #bfdbfe;
    }}

    .header-badge.accent {{
        background-color: #f0fdf4;
        color: #15803d;
        border-color: #bbf7d0;
    }}

    /* Callout Note */
    .callout {{
        border-radius: 6px;
        padding: 10px 14px;
        margin: 10px 0 14px 0;
        page-break-inside: avoid;
        break-inside: avoid;
    }}

    .callout-note {{
        background-color: #f8fafc;
        border-left: 4px solid #3b82f6;
        border-top: 1px solid #e2e8f0;
        border-right: 1px solid #e2e8f0;
        border-bottom: 1px solid #e2e8f0;
    }}

    .callout-badge {{
        display: flex;
        align-items: center;
        gap: 5px;
        font-size: 8pt;
        font-weight: 700;
        letter-spacing: 0.05em;
        color: #1d4ed8;
        margin-bottom: 4px;
    }}

    .callout-body p {{
        font-size: 8.8pt;
        color: #334155;
        line-height: 1.4;
    }}

    .callout-body em {{
        color: #0f172a;
        font-weight: 600;
        font-style: normal;
        background-color: #fef08a;
        padding: 0 3px;
        border-radius: 2px;
    }}

    /* Section Headings */
    h2 {{
        font-size: 11.5pt;
        font-weight: 700;
        color: #0f172a;
        margin-top: 14px;
        margin-bottom: 8px;
        padding-bottom: 4px;
        border-bottom: 1px solid #cbd5e1;
        display: flex;
        align-items: center;
        gap: 6px;
        page-break-after: avoid;
        break-after: avoid;
    }}

    hr {{
        display: none;
    }}

    /* Tables */
    table {{
        width: 100%;
        border-collapse: separate;
        border-spacing: 0;
        margin-bottom: 14px;
        font-size: 8.3pt;
        border: 1px solid #cbd5e1;
        border-radius: 6px;
        overflow: hidden;
    }}

    thead {{
        display: table-header-group;
    }}

    thead tr {{
        background-color: #0f172a;
        color: #ffffff;
    }}

    th {{
        padding: 7px 10px;
        font-weight: 600;
        text-align: left;
        letter-spacing: 0.02em;
        font-size: 8pt;
        border-bottom: 1px solid #334155;
    }}

    th:first-child {{ width: 25%; }}
    th:nth-child(2) {{ width: 22%; }}
    th:nth-child(3) {{ width: 53%; }}

    tbody tr {{
        page-break-inside: avoid;
        break-inside: avoid;
    }}

    tbody tr:nth-child(even) {{
        background-color: #f8fafc;
    }}

    tbody tr:nth-child(odd) {{
        background-color: #ffffff;
    }}

    td {{
        padding: 6.5px 10px;
        border-bottom: 1px solid #e2e8f0;
        vertical-align: top;
        line-height: 1.35;
    }}

    tbody tr:last-child td {{
        border-bottom: none;
    }}

    td.col-gcp {{
        color: #0f172a;
        font-weight: 600;
    }}

    td.col-gcp strong {{
        color: #1e40af;
        font-weight: 600;
    }}

    /* AWS Badge */
    .aws-pill {{
        display: inline-block;
        padding: 2px 7px;
        border-radius: 4px;
        background-color: #fff7ed;
        color: #9a3412;
        border: 1px solid #fed7aa;
        font-size: 7.8pt;
        font-weight: 500;
        white-space: normal;
    }}

    /* Exam Keyword Tag */
    .exam-kw-tag {{
        display: inline;
        font-weight: 700;
        color: #b45309;
    }}

    /* Decision Card */
    .decision-card {{
        background: #fdfefe;
        border: 1.5px solid #0284c7;
        border-radius: 6px;
        padding: 10px 14px;
        margin: 10px 0 16px 0;
        page-break-inside: avoid;
        break-inside: avoid;
    }}

    .decision-card-header {{
        display: flex;
        align-items: center;
        gap: 6px;
        margin-bottom: 8px;
    }}

    .decision-title {{
        font-size: 8.5pt;
        font-weight: 700;
        color: #0369a1;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }}

    .decision-flow {{
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 6px;
        margin-bottom: 8px;
    }}

    .step-badge {{
        background-color: #0284c7;
        color: #ffffff;
        font-weight: 600;
        font-size: 8pt;
        padding: 3px 9px;
        border-radius: 4px;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05);
    }}

    .step-arrow {{
        color: #0284c7;
        font-weight: 700;
        font-size: 9pt;
    }}

    .decision-note {{
        font-size: 8pt;
        color: #475569;
        font-style: italic;
        line-height: 1.35;
        border-top: 1px dashed #bae6fd;
        padding-top: 6px;
    }}

    /* Print Footer */
    .footer-note {{
        margin-top: 18px;
        font-size: 7.5pt;
        color: #94a3b8;
        text-align: center;
        border-top: 1px solid #f1f5f9;
        padding-top: 6px;
    }}
</style>
</head>
<body>

<div class="gcp-top-bar">
    <div class="bar-blue"></div>
    <div class="bar-red"></div>
    <div class="bar-yellow"></div>
    <div class="bar-green"></div>
</div>

<div class="header-container">
    <div class="header-title-area">
        <h1>GCP Professional Cloud Architect (PCA)</h1>
        <div class="header-subtitle">Service Cheatsheet &amp; AWS-to-GCP Architectural Decision Matrix</div>
    </div>
    <div class="header-badges">
        <span class="header-badge">PCA Cheat Sheet</span>
        <span class="header-badge accent">AWS Crosswalk</span>
    </div>
</div>

{body_content}

<div class="footer-note">
    Google Cloud Professional Cloud Architect (PCA) Reference • Generated for Study &amp; Cross-Cloud Architecture Mapping
</div>

</body>
</html>
"""

def main():
    if not MD_FILE.exists():
        print(f"Error: {MD_FILE} does not exist.")
        return 1

    text = MD_FILE.read_text(encoding="utf-8")
    
    # Strip main H1 since our template handles it in the header
    text_no_h1 = re.sub(r'^#\s+GCP Professional Cloud Architect.*?\n', '', text, count=1).strip()
    
    parsed_body = parse_markdown(text_no_h1)
    full_html = build_full_html(parsed_body)
    
    HTML_FILE.write_text(full_html, encoding="utf-8")
    print(f"Wrote styled HTML to: {HTML_FILE}")

    # Render PDF using headless Chrome
    chrome_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    if not os.path.exists(chrome_path):
        print(f"Warning: Chrome binary not found at {chrome_path}")
        return 0

    cmd = [
        chrome_path,
        "--headless=new",
        "--disable-gpu",
        "--no-pdf-header-footer",
        f"--print-to-pdf={PDF_FILE}",
        str(HTML_FILE)
    ]
    
    print("Executing:", " ".join(cmd))
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode == 0 and PDF_FILE.exists():
        print(f"Successfully generated PDF: {PDF_FILE} ({PDF_FILE.stat().st_size} bytes)")
    else:
        print(f"Chrome exited with code {res.returncode}")
        print("Stdout:", res.stdout)
        print("Stderr:", res.stderr)

    return 0

if __name__ == "__main__":
    main()
