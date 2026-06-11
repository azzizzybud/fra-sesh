import subprocess, json, os

code = '''
import json, sys
from modules.content_agent import ContentAgent, ContentBrief
brief = ContentBrief(angle="test topic", product="way_of_the_feather", format="short_form")
agent = ContentAgent()
result = agent.generate(brief)
out = {"status": "ok"}
out["script_preview"] = result.short_form.format_teleprompter()[:300] if result.short_form else "none"
out["hook_variants"] = {
    "curiosity_gap": result.hook_variants.curiosity_gap,
    "identity_mirror": result.hook_variants.identity_mirror,
    "authority_open": result.hook_variants.authority_open,
} if result.hook_variants else {}
print(json.dumps(out, ensure_ascii=False))
'''

fra_dir = r"C:\Users\info\OneDrive\Desktop\Claude-workspace\feather-research-agent"
env = os.environ.copy()
env["PYTHONPATH"] = fra_dir + os.pathsep + env.get("PYTHONPATH", "")

proc = subprocess.run(
    [r"C:\Users\info\OneDrive\Desktop\Claude-workspace\odysseus\venv\Scripts\python.exe", "-c", code],
    capture_output=True, text=True, timeout=30,
    cwd=fra_dir, env=env,
)
print("returncode:", proc.returncode)
if proc.stdout:
    print("stdout:", proc.stdout[:1000])
if proc.stderr:
    print("stderr:", proc.stderr[:1000])
