"""Live end-to-end test: runs 2 different transcripts through Intake -> Planning -> Review (+ correction loop).
Usage: API_URL=http://localhost:8000 python3 tests/e2e_live.py   (needs: pip install httpx)
"""
import httpx, sys, json
import os
B=os.getenv("API_URL","https://nexus-ops-coordinator-production.up.railway.app")
T={
"A":("Priya: We agreed to ship the mobile app beta by April 12. Dev owns the API; Marcus will handle QA. We can't use third-party analytics because of the privacy policy. Nobody mentioned who does app store submission. Budget is 30k.","All releases need security sign-off. No deploys on Fridays."),
"B":("Sam: The warehouse migration moves to Q3. Lena will lead vendor selection, deadline end of June. We must keep the old system running during cutover. Someone needs to decide on training, but no owner yet. Customer comms must be approved by legal.","Legal approval required for any customer communication. Max 2 vendors shortlisted.")}
c=httpx.Client(timeout=180)
def post(p): 
    r=c.post(B+p); 
    return r.status_code, (r.json() if r.headers.get("content-type","").startswith("application/json") else r.text)
for name,(tr,ru) in T.items():
    print(f"\n===== Transcript {name} =====")
    rid=c.post(B+"/run/start",json={"transcript":tr,"rules":ru}).json()["run_id"]
    code,i=post(f"/run/{rid}/intake"); print("intake",code,i["status"],i["error"],
        {k:len(v) for k,v in (i["output"] or {}).items() if isinstance(v,list)})
    if i["status"]!="done": continue
    for rnd in range(3):
        code,p=post(f"/run/{rid}/planning"); 
        labels=[t.get("label") for t in (p["output"] or {}).get("tasks",[])]
        print(f"planning r{rnd+1}",code,p["status"],p["error"],len(labels),{l:labels.count(l) for l in set(labels)})
        if p["status"]!="done": break
        code,r=post(f"/run/{rid}/review"); o=r.get("output") or {}
        print(f"review   r{rnd+1}",code,r["status"],r.get("error"),"approved=",o.get("approved"),"corrections=",len(o.get("corrections",[])))
        if r["status"]=="done": break
    s=c.get(B+f"/run/{rid}/status").json()
    fp=s["final_plan"]; print("final_plan:", "none" if not fp else [t["title"] for t in fp["tasks"]][:6])
