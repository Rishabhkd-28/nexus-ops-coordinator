import { useState, useEffect, useRef, useCallback } from "react";
import { api } from "./api";

// ── helpers ──────────────────────────────────────────────────────────────────
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const esc = (s) => String(s ?? "").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
const ts = () => new Date().toLocaleTimeString("en-GB", { hour12: false });

export default function App() {
  const [runId, setRunId]       = useState(null);
  const [session, setSession]   = useState(null);
  const [running, setRunning]   = useState(false);
  const [feed, setFeed]         = useState([]);
  const [view, setView]         = useState("pipe");   // pipe | conv | out
  const [leftTab, setLeftTab]   = useState("source"); // source | controls | config
  const [openNodes, setOpenNodes] = useState(new Set(["intake"]));
  const [simFail, setSimFail]   = useState(null);
  const [savedRules, setSavedRules] = useState("");
  const [transcript, setTranscript] = useState("");
  const [rules, setRules]       = useState("");
  const [editTxt, setEditTxt]   = useState("");

  const pollRef  = useRef(null);
  const feedRef  = useRef(null);

  // ── polling ────────────────────────────────────────────────────────────────
  const startPoll = useCallback((id) => {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      try { setSession(await api.status(id)); } catch {}
    }, 2000);
  }, []);
  const stopPoll = useCallback(() => {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
  }, []);

  // ── auto-advance ──────────────────────────────────────────────────────────
  useEffect(() => {
    if (!session || !runId) return;
    const { intake, planning, review } = session;
    const advance = async () => {
      try {
        if (intake?.status === "done" && planning?.status === "waiting") {
          addFeed("intake", `Extracted ${intake.output?.decisions?.length ?? 0} decisions, ${intake.output?.flags?.length ?? 0} flags. Schema validated ✓ — handing off to Planning.`, "handoff",
            JSON.stringify({ decisions: intake.output?.decisions?.length, requirements: intake.output?.requirements?.length, flags: intake.output?.flags?.length }, null, 2));
          addFeed("planning", "Received intake output. Building task plan from facts and company rules…", "planning");
          await api.planning(runId);
          setSession(await api.status(runId));
        } else if (planning?.status === "done" && review?.status === "waiting") {
          addFeed("planning", `Proposed ${planning.output?.tasks?.length ?? 0} tasks. Schema validated ✓ — handing off to Review.`, "handoff",
            JSON.stringify({ tasks: planning.output?.tasks?.length, unresolved: planning.output?.tasks?.filter(t=>t.label==="[UNRESOLVED]").length }, null, 2));
          addFeed("review", "Received draft plan. Auditing every task against the transcript and company rules…", "review");
          await api.review(runId);
          setSession(await api.status(runId));
        } else if (review?.status === "needs_revision" && planning?.status === "waiting") {
          addFeed("review", `Sending ${review.corrections?.length ?? 0} corrections back to Planning — revision round ${review.attempts}/2.`, "warn",
            JSON.stringify(review.corrections?.map(c=>({task:c.task_id,issue:c.issue.slice(0,50)})), null, 2));
          addFeed("planning", "Received corrections. Revising plan — only changing what Review flagged.", "planning");
          await api.planning(runId);
          setSession(await api.status(runId));
          setTimeout(async () => {
            addFeed("review", "Re-auditing revised plan…", "review");
            await api.review(runId);
            setSession(await api.status(runId));
          }, 500);
        } else if (review?.status === "done" || session.final_plan) {
          addFeed("review", review?.output?.approved
            ? "Plan approved ✓ All tasks grounded in transcript or rules. Owners assigned."
            : "Max revision rounds reached. Surfacing unresolved issues.", review?.output?.approved ? "ok" : "warn");
          addFeed("sys", "Pipeline complete. Final plan ready.", "sys");
          setRunning(false);
          stopPoll();
        } else if (["failed"].includes(intake?.status) || ["failed"].includes(planning?.status) || ["failed"].includes(review?.status)) {
          addFeed("sys", "Agent failed — see pipeline view for details and retry options.", "err");
          setRunning(false);
          stopPoll();
        }
      } catch (e) {
        addFeed("sys", `Error: ${e.message}`, "err");
        setRunning(false);
        stopPoll();
      }
    };
    advance();
  }, [session?.intake?.status, session?.planning?.status, session?.review?.status]);

  // ── feed ──────────────────────────────────────────────────────────────────
  const addFeed = (who, text, tag, payload) => {
    setFeed(f => [...f, { who, text, tag, payload, time: ts() }]);
    setTimeout(() => { if (feedRef.current) feedRef.current.scrollTop = feedRef.current.scrollHeight; }, 50);
  };

  // ── run ───────────────────────────────────────────────────────────────────
  const handleRun = async () => {
    if (!transcript.trim()) { alert("Please enter a transcript"); return; }
    if (!rules.trim())      { alert("Please enter company rules"); return; }
    setRunning(true);
    setFeed([]);
    setSession(null);
    try {
      addFeed("sys", "Starting new pipeline run…", "sys");
      const { run_id } = await api.start(transcript, rules);
      setRunId(run_id);
      addFeed("sys", `Session created: ${run_id}`, "sys");
      addFeed("intake", "Reading transcript — extracting only what is explicitly stated. No invented owners or deadlines.", "intake");
      await api.intake(run_id);
      const s = await api.status(run_id);
      setSession(s);
      startPoll(run_id);
    } catch (e) {
      addFeed("sys", `Failed to start: ${e.message}`, "err");
      setRunning(false);
    }
  };

  const handleReset = async () => {
    stopPoll();
    if (runId) await api.reset(runId).catch(() => {});
    setRunId(null); setSession(null); setRunning(false);
    setFeed([]); setSimFail(null); setOpenNodes(new Set(["intake"]));
  };

  const handleEditFact = async () => {
    if (!editTxt.trim() || !runId) return;
    addFeed("sys", `User corrected a fact: "${editTxt}" — intake context version bumped, rerunning Planning + Review.`, "warn");
    await api.editFact(runId, editTxt);
    setEditTxt("");
    setSession(await api.status(runId));
    setRunning(true);
    addFeed("planning", "Rerunning with updated intake context…", "planning");
    await api.planning(runId);
    setSession(await api.status(runId));
    addFeed("review", "Re-auditing after fact correction…", "review");
    await api.review(runId);
    setSession(await api.status(runId));
    addFeed("review", "Plan re-approved with corrected facts.", "ok");
    setRunning(false);
  };

  const handleSimFail = async (agent) => {
    if (!runId) return;
    setSimFail(agent);
    await api.simulateFailure(runId, agent);
    addFeed("sys", `Failure injected on ${agent} — next call will fail (simulated fault, clearly labelled).`, "warn");
  };
  const handleClearFail = async () => {
    setSimFail(null);
    if (runId) await api.clearFailure(runId);
  };

  const handleRetry = async (agent) => {
    if (!runId) return;
    addFeed("sys", `Retrying ${agent} agent. Previously completed steps will not be duplicated.`, "sys");
    setRunning(true);
    try {
      await api[agent](runId);
      setSession(await api.status(runId));
      startPoll(runId);
    } catch (e) {
      addFeed("sys", `Retry failed: ${e.message}`, "err");
      setRunning(false);
    }
  };

  const toggleNode = (key) => {
    setOpenNodes(prev => {
      const next = new Set(prev);
      next.has(key) ? next.delete(key) : next.add(key);
      return next;
    });
  };

  const loadSample = () => {
    setTranscript(`Project sync — Nexus Analytics, Nov 13 2026\n\nAlice: We've agreed to deliver the Q1 dashboard to the client by end of January.\nBob: I'll own the frontend build. We should use our standard React component library.\nAlice: Agreed. The backend API needs to be ready two weeks before the dashboard launches.\nCarol: We also need to integrate with the client's data warehouse — that's a hard requirement from their side.\nAlice: Right. And we have a strict rule — no third-party data connectors without security review first.\nBob: Who's handling the data pipeline work?\nAlice: We haven't decided that yet.\nCarol: I can take it but I'm already on two projects. Let's revisit next week.`);
    setRules(`Nexus Analytics — Company Rules\n\n1. Every task must have an assigned owner before work begins.\n2. Deadlines must be explicit dates, not relative terms like "soon" or "next week".\n3. No third-party integrations without a security review sign-off.\n4. All client deliverables must be reviewed by a senior engineer before release.\n5. Dependencies between tasks must be documented before sprint planning.\n6. If an owner is unavailable, an alternate must be named within 24 hours.`);
    setSavedRules(rules);
  };

  const ag = (key) => session?.[key] || { status: "waiting", output: null, error: null };

  return (
    <div id="app-root">
      {/* ── Topbar ── */}
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark">
            <svg viewBox="0 0 14 14" fill="none" stroke="white" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M2 7l3.5 3.5L12 3"/></svg>
          </div>
          <span className="brand-name">Nexus</span>
          <div className="brand-sep" />
          <span className="brand-sub">Operations Coordinator</span>
        </div>
        <div style={{flex:1}} />
        <div className="topbar-actions">
          <button className="btn btn-g" onClick={loadSample}>Load sample</button>
          <button className="btn btn-g" onClick={handleReset} disabled={!runId}>Reset</button>
          <button className={`btn btn-p${running?" go":""}`} onClick={handleRun} disabled={running}>
            {running ? "Running…" : "Run pipeline"}
          </button>
        </div>
      </header>

      {/* ── Workspace ── */}
      <div className="workspace">
        {/* LEFT */}
        <aside className="left-panel">
          <div className="lhead">
            <div className="lhead-t">Setup</div>
            <div className="ltabs">
              {["source","controls","config"].map(t => (
                <button key={t} className={`ltab${leftTab===t?" on":""}`} onClick={()=>setLeftTab(t)}>
                  {t.charAt(0).toUpperCase()+t.slice(1)}
                </button>
              ))}
            </div>
          </div>
          <div className="lbody">
            {leftTab === "source" && (
              <div>
                <label className="lbl" style={{marginTop:0}}>Meeting transcript</label>
                <div className="hint">Paste notes or a transcript — plain English, any format</div>
                <textarea className="tf" rows={9} value={transcript} onChange={e=>setTranscript(e.target.value)}
                  placeholder={"Alice said we'll ship the Q1 dashboard by end of January.\nBob will own the frontend build.\nNobody was assigned to the backend API yet."} />
                <label className="lbl" style={{marginTop:14}}>Company rules</label>
                <div className="hint">Policies the plan must follow</div>
                <textarea className="tf" rows={5} value={rules} onChange={e=>setRules(e.target.value)}
                  placeholder={"1. Every task must have an assigned owner before work begins.\n2. Deadlines must be specific dates.\n3. No third-party tools without a security review."} />
                <div className="field-actions">
                  <button className="bsm bcancel" onClick={()=>setRules(savedRules)}>Cancel</button>
                  <button className="bsm bsave" onClick={()=>{setSavedRules(rules);alert("Rules saved");}}>Save rules</button>
                </div>
                {runId && (
                  <div className="sstrip">
                    <span className="ss-lbl">Session</span>
                    <span className="ss-id">{runId}</span>
                    <span className="ss-live"><span/>Active</span>
                  </div>
                )}
              </div>
            )}
            {leftTab === "controls" && (
              <div>
                {!runId ? (
                  <div className="ctrl-empty">
                    <div style={{fontSize:13,fontWeight:700,color:"var(--ink3)",marginBottom:4}}>No active run</div>
                    <div>Start a pipeline run to unlock controls</div>
                  </div>
                ) : (
                  <>
                    <div className="editblk">
                      <label className="lbl" style={{color:"var(--violet)"}}>Correct a fact</label>
                      <div className="hint" style={{color:"rgba(109,40,217,.7)"}}>Describe what changed — Planning and Review will rerun</div>
                      <textarea className="tf" rows={2} value={editTxt} onChange={e=>setEditTxt(e.target.value)}
                        placeholder='e.g. "Assign Carol as owner of the backend API task"' />
                      <button className="ebtn" disabled={!editTxt.trim()} onClick={handleEditFact}>Apply and rerun</button>
                    </div>
                    <div className="cblk">
                      <div className="cblk-t">Simulate failure</div>
                      <select className="sel" id="sim-sel" defaultValue="intake">
                        <option value="intake">Intake agent</option>
                        <option value="planning">Planning agent</option>
                        <option value="review">Review agent</option>
                      </select>
                      <div className="sm-row">
                        <button className="smbtn smbtn-r" onClick={()=>handleSimFail(document.getElementById("sim-sel").value)}>Fail next call</button>
                        <button className="smbtn smbtn-g" onClick={handleClearFail}>Clear</button>
                      </div>
                      {simFail && (
                        <div className="simwarn">⚠ Next <strong>{simFail}</strong> call will fail (simulated fault)</div>
                      )}
                    </div>
                  </>
                )}
              </div>
            )}
            {leftTab === "config" && (
              <div>
                <label className="lbl">Backend URL</label>
                <input className="tf" defaultValue={import.meta.env.VITE_API_URL||"http://localhost:8000"} style={{marginBottom:14}}/>
                <label className="lbl">Model (set in backend .env)</label>
                <select className="sel" style={{marginBottom:14}}>
                  <option>google/gemma-3-27b-it:free</option>
                  <option>meta-llama/llama-3.1-8b-instruct:free</option>
                  <option>mistralai/mistral-7b-instruct:free</option>
                </select>
                <div style={{padding:"11px 13px",background:"var(--paper2)",border:"1px solid var(--line)",borderRadius:8,fontSize:12,color:"var(--ink3)",lineHeight:1.6}}>
                  All models are <strong style={{color:"var(--ink2)"}}>OpenRouter free tier</strong>. Add <code style={{fontFamily:"monospace",background:"var(--bg)",padding:"1px 5px",borderRadius:3}}>OPENROUTER_API_KEY</code> to backend <code style={{fontFamily:"monospace",background:"var(--bg)",padding:"1px 5px",borderRadius:3}}>.env</code>.
                </div>
              </div>
            )}
          </div>
        </aside>

        {/* RIGHT */}
        <div className="right-panel">
          {/* Floating tabs */}
          <div className="vtabs">
            {[["pipe","Pipeline"],["conv","What's happening"],["out","Final plan"]].map(([id,label])=>(
              <button key={id} className={`vtab${view===id?" on":""}`} onClick={()=>setView(id)}>
                {label}
                {id==="conv" && <span className="vc">{feed.length}</span>}
                {id==="out" && session?.final_plan && <span className="vc">●</span>}
              </button>
            ))}
          </div>

          <div className="vbody">
            {/* PIPELINE */}
            {view==="pipe" && (
              <div className="vp-pipe">
                {["intake","planning","review"].map((key, idx) => (
                  <div key={key}>
                    <AgentNode
                      agentKey={key} state={ag(key)}
                      open={openNodes.has(key)}
                      onToggle={()=>toggleNode(key)}
                      onRetry={()=>handleRetry(key)}
                    />
                    {idx < 2 && (
                      <div className="node-gap">
                        {key==="planning" && (ag("review").status==="needs_revision"||ag("review").status==="revision") && (
                          <div className="loop-lbl">↺ revision loop</div>
                        )}
                        <div className={`edge-line ${ag(key).status==="running"?"edge-active":ag(key).status==="done"?"edge-done":""}`} />
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}

            {/* WHAT'S HAPPENING */}
            {view==="conv" && (
              <div className="vp-conv" ref={feedRef}>
                <div className="conv-h">
                  <h3>What's happening</h3>
                  <p>Plain-English commentary from each agent — decisions made, things flagged, handoffs and corrections in real time.</p>
                </div>
                {feed.length === 0 ? (
                  <div className="feed-empty">
                    <div className="fe-t">Nothing yet</div>
                    <div className="fe-s">Run the pipeline and watch the agents work</div>
                  </div>
                ) : (
                  feed.map((msg, i) => <FeedMsg key={i} {...msg} />)
                )}
              </div>
            )}

            {/* FINAL PLAN */}
            {view==="out" && (
              <div className="vp-out">
                {!session?.final_plan ? (
                  <div className="out-empty">
                    <div className="oe-t">No plan yet</div>
                    <div className="oe-s">Run the pipeline to generate a reviewed action plan from your transcript</div>
                  </div>
                ) : (
                  <FinalPlan plan={session.final_plan} />
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// ── AgentNode ────────────────────────────────────────────────────────────────
function AgentNode({ agentKey, state, open, onToggle, onRetry }) {
  const meta = {
    intake:   { name: "Intake",   sub: "extract · classify · flag conflicts", icon: "blue" },
    planning: { name: "Planning", sub: "propose · label · sequence tasks",   icon: "violet" },
    review:   { name: "Review",   sub: "audit · correct · approve plan",     icon: "green" },
  }[agentKey];
  const { status, output, error, corrections, attempts } = state;
  const stClass = {waiting:"",running:" r",done:" d",failed:" f",needs_revision:" v"}[status]||"";

  return (
    <div className={`nc${stClass}`}>
      <div className="ncbar" />
      <div className="nh" onClick={onToggle}>
        <div className={`nav na-${agentKey}`}>
          <NodeIcon k={agentKey} />
        </div>
        <div className="ni">
          <div className="ni-name">{meta.name}</div>
          <div className="ni-sub">{meta.sub}</div>
        </div>
        <div className="nr">
          <StatusBadge status={status} />
          <svg className="chv" style={{transform:open?"":"rotate(-90deg)"}} viewBox="0 0 24 24" fill="none" stroke="var(--ink3)" strokeWidth="2"><polyline points="6 9 12 15 18 9"/></svg>
        </div>
      </div>
      {open && (
        <div className="nb open">
          <NodeBody agentKey={agentKey} status={status} output={output} error={error}
            corrections={corrections} attempts={attempts} onRetry={onRetry} />
        </div>
      )}
    </div>
  );
}

function StatusBadge({ status }) {
  const map = {
    waiting:        { cls: "sb-idle", label: "Waiting" },
    running:        { cls: "sb-run",  label: "Running…" },
    done:           { cls: "sb-done", label: "Done" },
    failed:         { cls: "sb-fail", label: "Failed" },
    needs_revision: { cls: "sb-rev",  label: "Revision" },
  };
  const { cls, label } = map[status] || map.waiting;
  return <span className={`sb ${cls}`}><span className="sd"/>{label}</span>;
}

function NodeIcon({ k }) {
  if (k==="intake")   return <svg viewBox="0 0 24 24" stroke="#3b82f6" fill="none" strokeWidth="1.7" width="17" height="17"><path d="M9 11l3 3L22 4"/><path d="M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11"/></svg>;
  if (k==="planning") return <svg viewBox="0 0 24 24" stroke="#8b5cf6" fill="none" strokeWidth="1.7" width="17" height="17"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/></svg>;
  return <svg viewBox="0 0 24 24" stroke="#22c55e" fill="none" strokeWidth="1.7" width="17" height="17"><path d="M22 11.08V12a10 10 0 11-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>;
}

function NodeBody({ agentKey, status, output, error, corrections, attempts, onRetry }) {
  if (status === "running") return <div className="n-run"><div className="spinner"/>{{intake:"Reading transcript — extracting decisions, requirements and constraints…",planning:"Building task plan from intake output and company rules…",review:"Auditing plan against transcript and company rules…"}[agentKey]}</div>;
  if (status === "failed")  return <div className="nerr"><div className="nerr-t">Agent failed</div><div className="nerr-m">{error}</div><button className="retry-btn" onClick={onRetry}>Retry — resume without duplicating completed steps</button></div>;
  if (!output)              return <div className="n-idle"><div className="idots"><span/><span/><span/></div>{{intake:"Waiting for run",planning:"Waiting for Intake",review:"Waiting for Planning"}[agentKey]}</div>;

  if (agentKey === "intake") return <IntakeBody output={output} />;
  if (agentKey === "planning") return <PlanningBody output={output} corrections={corrections} />;
  return <ReviewBody output={output} attempts={attempts} />;
}

function IntakeBody({ output }) {
  const o = output;
  return (
    <div>
      <div className="hv-strip hv-ok">✓ Output schema validated — {(o.decisions?.length||0)+(o.requirements?.length||0)+(o.constraints?.length||0)} items extracted, {o.flags?.length||0} flag(s)</div>
      <div className="statrow">
        {[["decisions",o.decisions?.length,"var(--blue)"],["requirements",o.requirements?.length,"var(--violet)"],["constraints",o.constraints?.length,"var(--amber)"],["flags",o.flags?.length,"var(--red)"]].map(([l,n,c])=>(
          <div key={l} className="sc"><div className="scn" style={{color:c}}>{n||0}</div><div className="scl">{l}</div></div>
        ))}
      </div>
      {o.decisions?.length > 0 && <><div className="sec" style={{color:"var(--blue)"}}>Decisions</div>{o.decisions.map((d,i)=><div key={i} className="item"><div className="im" style={{background:"var(--blue)"}}/><div className="ib"><div className="it">{d.text}</div>{d.source_ref&&<div className="ir">Source: "{d.source_ref}"</div>}{d.owner&&<div className="io">👤 {d.owner}{d.deadline?" · 📅 "+d.deadline:""}</div>}</div></div>)}</>}
      {o.requirements?.length > 0 && <><div className="sec" style={{color:"var(--violet)"}}>Requirements</div>{o.requirements.map((r,i)=><div key={i} className="item"><div className="im" style={{background:"var(--violet)"}}/><div className="ib"><div className="it">{r.text}</div>{r.source_ref&&<div className="ir">Source: "{r.source_ref}"</div>}</div></div>)}</>}
      {o.constraints?.length > 0 && <><div className="sec" style={{color:"var(--amber)"}}>Constraints</div>{o.constraints.map((c,i)=><div key={i} className="item"><div className="im" style={{background:"var(--amber)"}}/><div className="ib"><div className="it">{c.text}</div></div></div>)}</>}
      {o.flags?.length > 0 && <><div className="sec" style={{color:"var(--red)"}}>Flags</div>{o.flags.map((f,i)=><div key={i} className={`flag flag-${f.type==="MISSING"?"miss":"conf"}`}><div className="ftag">{f.type}</div><div className="ft">{f.description}</div></div>)}</>}
      {o.user_edits?.length > 0 && <div style={{marginTop:10,padding:"8px 11px",background:"var(--violet-s)",border:"1px solid var(--violet-m)",borderRadius:7,fontSize:12,color:"var(--violet)",fontWeight:600}}>{o.user_edits.length} manual edit(s) applied to this context version</div>}
    </div>
  );
}

function PlanningBody({ output, corrections }) {
  const o = output;
  return (
    <div>
      {corrections?.length > 0 && (
        <div className="corrbx">
          <div className="corrbx-t">Corrections received from Review</div>
          {corrections.map((c,i)=><div key={i} className="corrln"><strong>Task {c.task_id}:</strong> {c.issue} — {c.suggested_fix}</div>)}
        </div>
      )}
      <div className="hv-strip hv-ok">✓ Handoff schema validated — {o.tasks?.length||0} tasks proposed</div>
      {o.tasks?.map((t,i)=>{
        const lc = t.label==="[SUPPORTED]"?"lsup":t.label==="[RECOMMENDED]"?"lrec":"lunr";
        return (
          <div key={t.id} className="tc" style={{animationDelay:`${i*35}ms`}}>
            <div className="tc-h">
              <div style={{flex:1,minWidth:0}}><div className="tc-title">{t.title}</div><div className="tc-desc">{t.description}</div></div>
              <div className={`tlbl ${lc}`}>{t.label}</div>
            </div>
            <div className="tc-m">
              <div className={`tmi${!t.owner?" red":""}`}>👤 {t.owner||<span style={{color:"var(--red)",fontWeight:600}}>Unassigned</span>}</div>
              <div className="tmi">📅 {t.deadline||<span style={{color:"var(--amber)",fontWeight:600}}>No date</span>}</div>
              {t.depends_on?.length > 0 && <div className="tmi">🔗 {t.depends_on.join(", ")}</div>}
            </div>
          </div>
        );
      })}
      {o.corrections_addressed?.length > 0 && (
        <div style={{marginTop:10,padding:"9px 11px",background:"var(--green-s)",border:"1px solid var(--green-m)",borderRadius:7}}>
          <div style={{fontSize:11,fontWeight:700,color:"var(--green)",marginBottom:5}}>Corrections addressed</div>
          {o.corrections_addressed.map((c,i)=><div key={i} style={{fontSize:12,color:"var(--green)",marginBottom:3}}>✓ {c}</div>)}
        </div>
      )}
    </div>
  );
}

function ReviewBody({ output, attempts }) {
  const o = output;
  return (
    <div>
      {attempts > 0 && (
        <div className="att-row">
          <div className="pips">{[0,1].map(i=><div key={i} className={`pip${i<attempts?(o.approved&&i===attempts-1?" g":" a"):""}`}/>)}</div>
          Round {attempts}/2
        </div>
      )}
      <div className={`verdict ${o.approved?"v-pass":"v-fail"}`}>
        <div className="v-head">
          <div className="v-ic">
            {o.approved ? <svg viewBox="0 0 24 24" stroke="white" fill="none" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
                        : <svg viewBox="0 0 24 24" stroke="white" fill="none" strokeWidth="2"><path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/></svg>}
          </div>
          <div className="v-title">{o.approved ? "Plan approved" : "Corrections required"}</div>
        </div>
        <div className="v-sum">{o.summary}</div>
      </div>
      {!o.approved && o.corrections?.map((c,i)=>(
        <div key={i} className="revi">
          <div className="revi-task">Task {c.task_id}</div>
          <div className="revi-iss">{c.issue}</div>
          <div className="revi-rule">{c.rule_or_ref}</div>
        </div>
      ))}
    </div>
  );
}

// ── FeedMsg ──────────────────────────────────────────────────────────────────
const FAV = {intake:"fav1",planning:"fav2",review:"fav3",sys:"favs"};
const FTAG = {intake:"ftag-i",planning:"ftag-p",review:"ftag-r",sys:"ftag-s",warn:"ftag-w",ok:"ftag-ok",err:"ftag-err",handoff:"ftag-hd"};
const FNAME = {intake:"Intake agent",planning:"Planning agent",review:"Review agent",sys:"System"};
const TAGLABEL = {intake:"Extracting",planning:"Planning",review:"Auditing",sys:"System",warn:"Warning",ok:"Approved",err:"Failed",handoff:"Handoff"};

function FeedMsg({ who, text, tag, payload, time }) {
  const [showPayload, setShowPayload] = useState(false);
  return (
    <div className="fmsg">
      <div className={`fav ${FAV[who]||"favs"}`}><NodeIcon k={who}/></div>
      <div className="fright">
        <div className="fwho">
          <span className="fname">{FNAME[who]||who}</span>
          <span className="ftime">{time}</span>
          <span className={`ftag2 ${FTAG[tag]||"ftag-s"}`}>{TAGLABEL[tag]||tag}</span>
        </div>
        <div className="ftxt" dangerouslySetInnerHTML={{__html: text}} />
        {payload && (
          <div>
            <button onClick={()=>setShowPayload(p=>!p)} style={{fontSize:10,color:"var(--ink4)",background:"none",border:"none",cursor:"pointer",marginTop:4,padding:0,textDecoration:"underline"}}>
              {showPayload?"Hide":"Show"} handoff payload
            </button>
            {showPayload && <pre className="handoff-preview">{payload}</pre>}
          </div>
        )}
      </div>
    </div>
  );
}

// ── FinalPlan ────────────────────────────────────────────────────────────────
function FinalPlan({ plan }) {
  const sup = plan.tasks?.filter(t=>t.label==="[SUPPORTED]").length||0;
  const rec = plan.tasks?.filter(t=>t.label==="[RECOMMENDED]").length||0;
  const unr = plan.tasks?.filter(t=>t.label==="[UNRESOLVED]").length||0;
  return (
    <div>
      <div className="out-hero">
        <div className="oh-bg"/>
        <div className="oh-ey">final plan · review-approved · {new Date().toLocaleDateString("en-US",{month:"long",day:"numeric",year:"numeric"})}</div>
        <div className="oh-title">Action plan</div>
        <div className="oh-sub">Nexus Analytics · generated from meeting transcript · {plan.tasks?.length||0} tasks</div>
      </div>
      <div className="ostat-row">
        {[[plan.tasks?.length||0,"Total tasks","var(--ink)",""],[sup,"Supported","var(--green)","From transcript"],[rec,"Recommended","var(--blue)","From rules"],[unr,"Unresolved","var(--amber)",unr?"Needs action":"All clear"]].map(([n,l,c,t],i)=>(
          <div key={i} className="ostat"><div className="ostat-n" style={{color:c}}>{n}</div><div className="ostat-l">{l}</div>{t&&<div className={`ostat-t ${c===`var(--green)`||t==="All clear"?"g":"a"}`}>{t}</div>}</div>
        ))}
      </div>
      {plan.tasks?.map((t,i)=>{
        const lc = t.label==="[SUPPORTED]"?"lsup":t.label==="[RECOMMENDED]"?"lrec":"lunr";
        return (
          <div key={t.id} className="ot" style={{animationDelay:`${i*45}ms`}}>
            <div className="ot-idx">{String(i+1).padStart(2,"0")}</div>
            <div>
              <div className="ot-name">{t.title}</div>
              <div className="ot-row">
                <div className={`omi${!t.owner?" red":""}`}>👤 {t.owner||"Unassigned"}</div>
                <div className="omi">📅 {t.deadline||"No deadline"}</div>
                <div className="omi">{t.description?.slice(0,65)}…</div>
              </div>
            </div>
            <span className={`tlbl ${lc}`}>{t.label}</span>
          </div>
        );
      })}
    </div>
  );
}
