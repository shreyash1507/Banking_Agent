import re
import sys

with open("index.html", "r", encoding="utf-8") as f:
    content = f.read()

# 1. Update the sidebar navigation
# Let's add the live bots under a new section or replace the existing policy/loan bots.
# Look for: <div class="nav-section">INTERNAL OPERATIONS</div>
nav_addition = """
        <div class="nav-section">LIVE BOTS (API INTEGRATED)</div>
        <div class="nav-item nav-sub" onclick="showTab('live-policy')">
          <div style="display:flex;align-items:center;gap:8px">
            <div style="width:16px;height:16px;border-radius:4px;background:rgba(46,204,113,0.15);display:flex;align-items:center;justify-content:center;color:var(--green)">
              <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>
            </div>
            Policy Bot
          </div>
        </div>
        <div class="nav-item nav-sub" onclick="showTab('live-loan')">
          <div style="display:flex;align-items:center;gap:8px">
            <div style="width:16px;height:16px;border-radius:4px;background:rgba(46,204,113,0.15);display:flex;align-items:center;justify-content:center;color:var(--green)">
              <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>
            </div>
            Loan Eligibility Bot
          </div>
        </div>
"""

# Insert before <div class="nav-section">INTERNAL OPERATIONS</div>
content = content.replace('<div class="nav-section">INTERNAL OPERATIONS</div>', nav_addition + '\n        <div class="nav-section">INTERNAL OPERATIONS</div>')

# 2. Add the CSS for our visualizer
css_addition = """
    /* --- NEW LIVE BOTS CSS --- */
    .live-bot-container {
      display: flex;
      flex-direction: column;
      gap: 20px;
      height: calc(100vh - 120px);
    }
    .live-bot-input-area {
      background: var(--surface);
      border: 1px solid var(--border-subtle);
      border-radius: 8px;
      padding: 20px;
    }
    .live-bot-input {
      width: 100%;
      padding: 12px 16px;
      background: var(--surface2);
      border: 1px solid var(--border-subtle);
      color: var(--white);
      border-radius: 6px;
      font-size: 14px;
      font-family: inherit;
      outline: none;
      transition: all 0.2s;
    }
    .live-bot-input:focus {
      border-color: var(--ey-yellow);
      box-shadow: 0 0 0 2px rgba(255, 230, 0, 0.1);
    }
    .live-bot-btn {
      margin-top: 10px;
      background: var(--ey-yellow);
      color: var(--navy);
      font-weight: 600;
      padding: 10px 24px;
      border-radius: 6px;
      border: none;
      cursor: pointer;
      font-size: 14px;
      transition: opacity 0.2s;
    }
    .live-bot-btn:hover { opacity: 0.9; }
    .live-bot-btn:disabled { opacity: 0.5; cursor: not-allowed; }
    
    .live-bot-results {
      flex: 1;
      display: flex;
      gap: 20px;
      overflow: hidden;
    }
    .live-bot-graph, .live-bot-final {
      background: var(--surface);
      border: 1px solid var(--border-subtle);
      border-radius: 8px;
      padding: 20px;
      overflow-y: auto;
      flex: 1;
    }
    
    .graph-node {
      background: var(--surface2);
      border-left: 3px solid var(--ey-yellow);
      border-radius: 4px;
      padding: 12px;
      margin-bottom: 12px;
      position: relative;
    }
    .graph-node::before {
      content: '';
      position: absolute;
      left: 16px;
      top: -12px;
      height: 12px;
      width: 2px;
      background: var(--border-subtle);
    }
    .graph-node:first-child::before { display: none; }
    .node-header {
      font-family: 'IBM Plex Mono', monospace;
      font-size: 11px;
      color: var(--slate);
      margin-bottom: 6px;
      display: flex;
      justify-content: space-between;
    }
    .node-content {
      font-size: 13px;
      color: var(--white);
      white-space: pre-wrap;
      word-wrap: break-word;
    }
    .final-output-text {
      font-size: 15px;
      line-height: 1.6;
      color: var(--white);
      white-space: pre-wrap;
    }
    .loader {
      border: 3px solid var(--surface2);
      border-top: 3px solid var(--ey-yellow);
      border-radius: 50%;
      width: 24px;
      height: 24px;
      animation: spin 1s linear infinite;
      margin: 20px auto;
    }
    @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
"""
content = content.replace("</style>", css_addition + "\n  </style>")

# 3. Add the HTML panes
panes_addition = """
      <!-- LIVE POLICY BOT -->
      <div class="tab-pane" id="tab-live-policy">
        <div class="page-header">
          <div class="page-header-top">
            <div>
              <div class="page-title">Policy Bot (Live API)</div>
              <div class="page-subtitle">Interact with the PolicyRAGAgent in real-time. Enter a query to see the multi-agent orchestration.</div>
            </div><span class="page-tag tag-agentic">Live API</span>
          </div>
        </div>
        <div class="live-bot-container">
          <div class="live-bot-input-area">
            <input type="text" id="input-policy" class="live-bot-input" placeholder="e.g., What are the rules for dormant accounts?">
            <button class="live-bot-btn" id="btn-policy" onclick="runLiveQuery('policy')">Ask Policy Bot</button>
          </div>
          <div class="live-bot-results">
            <div class="live-bot-graph">
              <h3 style="font-size:14px;color:var(--slate);margin-bottom:12px;font-family:'IBM Plex Mono',monospace">Agent Thought Graph</h3>
              <div id="graph-policy"></div>
            </div>
            <div class="live-bot-final">
              <h3 style="font-size:14px;color:var(--slate);margin-bottom:12px;font-family:'IBM Plex Mono',monospace">Final Synthesized Output</h3>
              <div id="final-policy" class="final-output-text">Results will appear here...</div>
            </div>
          </div>
        </div>
      </div>

      <!-- LIVE LOAN BOT -->
      <div class="tab-pane" id="tab-live-loan">
        <div class="page-header">
          <div class="page-header-top">
            <div>
              <div class="page-title">Loan Eligibility Bot (Live API)</div>
              <div class="page-subtitle">Interact with the LoanEligibilityRAGAgent in real-time. It uses decision matrices to assess eligibility.</div>
            </div><span class="page-tag tag-agentic">Live API</span>
          </div>
        </div>
        <div class="live-bot-container">
          <div class="live-bot-input-area">
            <input type="text" id="input-loan" class="live-bot-input" placeholder="e.g., Calculate max personal loan for 35k income and 12k existing EMI">
            <button class="live-bot-btn" id="btn-loan" onclick="runLiveQuery('loan')">Assess Eligibility</button>
          </div>
          <div class="live-bot-results">
            <div class="live-bot-graph">
              <h3 style="font-size:14px;color:var(--slate);margin-bottom:12px;font-family:'IBM Plex Mono',monospace">Agent Thought Graph</h3>
              <div id="graph-loan"></div>
            </div>
            <div class="live-bot-final">
              <h3 style="font-size:14px;color:var(--slate);margin-bottom:12px;font-family:'IBM Plex Mono',monospace">Final Synthesized Output</h3>
              <div id="final-loan" class="final-output-text">Results will appear here...</div>
            </div>
          </div>
        </div>
      </div>
"""
content = content.replace("<!-- MODALS -->", panes_addition + "\n  <!-- MODALS -->")

# 4. Add the Javascript logic
js_addition = """
    // --- LIVE API LOGIC ---
    let sessionIds = { policy: null, loan: null };

    async function runLiveQuery(type) {
      const inputEl = document.getElementById(`input-${type}`);
      const btnEl = document.getElementById(`btn-${type}`);
      const graphEl = document.getElementById(`graph-${type}`);
      const finalEl = document.getElementById(`final-${type}`);
      
      const query = inputEl.value.trim();
      if (!query) return;

      // Reset UI
      btnEl.disabled = true;
      btnEl.textContent = "Processing...";
      graphEl.innerHTML = '<div class="loader"></div><div style="text-align:center;color:var(--slate-dim);font-size:12px;margin-top:10px">Orchestrating Agents...</div>';
      finalEl.innerHTML = '';

      try {
        const payload = { query: query };
        if (sessionIds[type]) payload.session_id = sessionIds[type];

        // Always call /api/v1/chat as requested
        const response = await fetch('http://localhost:8000/api/v1/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });

        if (!response.ok) {
          throw new Error(`Server returned ${response.status}: ${await response.text()}`);
        }

        const data = await response.json();
        sessionIds[type] = data.session_id;

        renderLiveGraph(graphEl, data.intermediate_steps);
        finalEl.innerHTML = data.final ? data.final.replace(/\\n/g, '<br>') : "No final output returned.";

      } catch (err) {
        graphEl.innerHTML = `<div style="color:var(--red);padding:10px;border:1px solid var(--red);border-radius:4px">Error: ${err.message}</div>`;
        finalEl.innerHTML = '';
      } finally {
        btnEl.disabled = false;
        btnEl.textContent = type === 'policy' ? "Ask Policy Bot" : "Assess Eligibility";
        inputEl.value = '';
      }
    }

    function renderLiveGraph(container, steps) {
      if (!steps || !steps.length) {
        container.innerHTML = '<div style="color:var(--slate-dim)">No intermediate steps available.</div>';
        return;
      }
      
      let html = '';
      steps.forEach((step, idx) => {
        let inputStr = typeof step.input === 'object' ? JSON.stringify(step.input, null, 2) : step.input;
        let outputStr = typeof step.output === 'object' ? JSON.stringify(step.output, null, 2) : step.output;
        
        html += `<div class="graph-node" style="animation:fadeIn 0.4s ease-out ${idx * 0.15}s both">
          <div class="node-header">
            <span style="color:var(--teal)">Agent: ${step.agent}</span>
            <span>Step ${idx + 1}</span>
          </div>
          <div class="node-content">
            <div style="color:var(--slate-dim);margin-bottom:4px"><strong>Input:</strong></div>
            <div style="background:rgba(0,0,0,0.2);padding:6px;border-radius:4px;margin-bottom:8px;font-family:'IBM Plex Mono',monospace;font-size:11px">${inputStr}</div>
            <div style="color:var(--slate-dim);margin-bottom:4px"><strong>Output:</strong></div>
            <div style="background:rgba(0,0,0,0.2);padding:6px;border-radius:4px;font-family:'IBM Plex Mono',monospace;font-size:11px;color:var(--green)">${outputStr}</div>
          </div>
        </div>`;
      });
      container.innerHTML = html;
    }
"""
content = content.replace("// ── INIT ──", js_addition + "\n    // ── INIT ──")

with open("index.html", "w", encoding="utf-8") as f:
    f.write(content)
